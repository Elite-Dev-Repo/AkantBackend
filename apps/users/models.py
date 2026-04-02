import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager







class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()





class AccountDetails(models.Model):
    id =  id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=15)
    bank_name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_details_user", null=True, blank=True)

    class Meta:
        db_table = "account_details"

    def __str__(self):
        return f"{self.account_name} <{self.account_number}>"
    