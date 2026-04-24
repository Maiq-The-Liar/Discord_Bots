from __future__ import annotations

import discord

HEAD_STUDENT_ROLE_NAME = "Head Student"


def is_admin_member(member: discord.abc.User | discord.Member) -> bool:
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def is_head_student(member: discord.abc.User | discord.Member) -> bool:
    return isinstance(member, discord.Member) and any(
        role.name == HEAD_STUDENT_ROLE_NAME for role in member.roles
    )


def is_admin_or_head_student(member: discord.abc.User | discord.Member) -> bool:
    return is_admin_member(member) or is_head_student(member)
