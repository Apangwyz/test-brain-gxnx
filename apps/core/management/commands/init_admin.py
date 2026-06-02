"""
初始化默认管理员用户

用法: python3 manage.py init_admin

创建默认管理员账号用于登录 TestBrain 平台。
如果用户已存在则跳过。
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "初始化默认管理员用户（admin / admin123）"

    def handle(self, *args, **options):
        User = get_user_model()
        username = "admin"
        password = "admin123"
        email = "admin@testbrain.local"

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f"用户 '{username}' 已存在，跳过创建"
            ))
            return

        User.objects.create_superuser(
            username=username,
            password=password,
            email=email,
        )
        self.stdout.write(self.style.SUCCESS(
            f"默认管理员用户创建成功！\n"
            f"  用户名: {username}\n"
            f"  密码:   {password}\n\n"
            f"请及时修改密码以保障安全。"
        ))
