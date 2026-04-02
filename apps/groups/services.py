"""
Groups service layer — all business logic lives here, not in views.
"""
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Group, GroupMembership, GroupInvite
from apps.users.models import User


class GroupService:

    @staticmethod
    @transaction.atomic
    def create_group(name: str, description: str, created_by: User, avatar=None) -> Group:
        group = Group.objects.create(
            name=name,
            description=description,
            created_by=created_by,
            avatar=avatar,
        )
        # Creator becomes admin automatically
        GroupMembership.objects.create(
            group=group,
            user=created_by,
            role=GroupMembership.Role.ADMIN,
        )
        return group

    @staticmethod
    def get_user_groups(user: User):
        return Group.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
            is_active=True,
        ).distinct()

    @staticmethod
    def get_active_members(group: Group):
        return GroupMembership.objects.filter(
            group=group, is_active=True
        ).select_related("user")

    @staticmethod
    @transaction.atomic
    def invite_member(group: Group, invited_by: User, invited_email: str) -> GroupInvite:
        # Check if already a member
        try:
            invited_user = User.objects.get(email=invited_email)
            if GroupMembership.objects.filter(group=group, user=invited_user, is_active=True).exists():
                raise ValueError("This user is already a member of the group.")
        except User.DoesNotExist:
            invited_user = None

        # Invalidate previous pending invites for same email/group
        GroupInvite.objects.filter(
            group=group,
            invited_email=invited_email,
            status=GroupInvite.Status.PENDING,
        ).update(status=GroupInvite.Status.EXPIRED)

        invite = GroupInvite.objects.create(
            group=group,
            invited_by=invited_by,
            invited_email=invited_email,
            invited_user=invited_user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Send invite email via Resend
        GroupService._send_invite_email(invite)

        return invite

    @staticmethod
    def _send_invite_email(invite: GroupInvite):
        """Send invite email using Resend."""
        import os
        import resend
        from django.conf import settings

        api_key = getattr(settings, "RESEND_API_KEY", None)

        if not api_key:
            print(f"[INVITE] No RESEND_API_KEY found in settings. Invite token: {invite.token}")
            return

        resend.api_key = api_key

        frontend_url = getattr(settings, "FRONTEND_URL", "https://akant.vercel.app")
        invite_link = f"{frontend_url}/invite/accept?token={invite.token}"
        inviter_name = invite.invited_by.full_name or invite.invited_by.username
        group_name = invite.group.name
        email_from = getattr(settings, "EMAIL_FROM", "akant Team <onboarding@resend.dev>")

        try:
            resend.Emails.send({
                "from": email_from,
                "to": [invite.invited_email],
                "subject": f"You've been invited to join {group_name} on akant",
                "html": f"""
                    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                        <h2 style="color: #16a34a;">You've been invited! 🎉</h2>
                        <p>
                            <strong>{inviter_name}</strong> has invited you to join
                            the group <strong>"{group_name}"</strong> on akant.
                        </p>
                        <p>akant makes splitting expenses effortless — track who owes what and settle up instantly.</p>
                        <a href="{invite_link}"
                           style="display:inline-block; background:#16a34a; color:white;
                                  padding:12px 24px; border-radius:8px; text-decoration:none;
                                  font-weight:bold; margin: 16px 0;">
                            Accept Invitation
                        </a>
                        <p style="color:#888; font-size:13px;">
                            This invite expires in 7 days.<br>
                            Or copy this link: {invite_link}
                        </p>
                        <hr style="border:none; border-top:1px solid #eee;">
                        <p style="color:#aaa; font-size:12px;">— The akantTeam</p>
                    </div>
                """,
                "text": f"""
{inviter_name} has invited you to join "{group_name}" on akant.

Accept your invitation here:
{invite_link}

This invite expires in 7 days.

— The akant Team
                """.strip(),
            })
            print(f"[INVITE] Email sent to {invite.invited_email}")
        except Exception as e:
            # Don't crash the invite creation if email fails
            print(f"[INVITE] Email failed: {e}. Token: {invite.token}")




    @staticmethod
    @transaction.atomic
    def accept_invite(token: str, user: User) -> GroupMembership:
        try:
            invite = GroupInvite.objects.select_related("group").get(
                token=token,
                status=GroupInvite.Status.PENDING,

            )
        except GroupInvite.DoesNotExist:
            raise ValueError("Invalid or expired invite token.")

        if invite.expires_at < timezone.now():
            invite.status = GroupInvite.Status.EXPIRED
            invite.save(update_fields=["status"])
            raise ValueError("This invite has expired.")

        if invite.invited_email != user.email:
            raise ValueError("This invite was not sent to your email address.")

        # Re-activate if previously left, else create
        membership, created = GroupMembership.objects.get_or_create(
            group=invite.group,
            user=user,
            defaults={"role": GroupMembership.Role.MEMBER},
        )
        if not created:
            membership.is_active = True
            membership.save(update_fields=["is_active"])

        invite.status = GroupInvite.Status.ACCEPTED
        invite.invited_user = user
        invite.save(update_fields=["status", "invited_user"])

        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(group: Group, user_to_remove: User, requesting_user: User):
        if user_to_remove == requesting_user:
            membership = GroupMembership.objects.get(
                group=group, user=user_to_remove, is_active=True
            )
            membership.is_active = False
            membership.save(update_fields=["is_active"])
            return

        requesting_membership = GroupMembership.objects.filter(
            group=group, user=requesting_user, role=GroupMembership.Role.ADMIN, is_active=True
        ).first()
        if not requesting_membership:
            raise PermissionError("Only group admins can remove members.")

        membership = GroupMembership.objects.filter(
            group=group, user=user_to_remove, is_active=True
        ).first()
        if not membership:
            raise ValueError("This user is not an active member of the group.")

        membership.is_active = False
        membership.save(update_fields=["is_active"])

    @staticmethod
    def promote_to_admin(group: Group, user: User, requesting_user: User):
        GroupService._assert_admin(group, requesting_user)
        membership = GroupMembership.objects.get(group=group, user=user, is_active=True)
        membership.role = GroupMembership.Role.ADMIN
        membership.save(update_fields=["role"])
        return membership

    @staticmethod
    def _assert_admin(group: Group, user: User):
        if not GroupMembership.objects.filter(
            group=group, user=user, role=GroupMembership.Role.ADMIN, is_active=True
        ).exists():
            raise PermissionError("Only group admins can perform this action.")
