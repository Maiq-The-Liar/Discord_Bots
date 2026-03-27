import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from domain.constants import HOUSE_ROLE_IDS, ARENA_ROLE_ID
from domain.role_context import MemberRoleContext
from repositories.user_repository import UserRepository
from repositories.inventory_repository import InventoryRepository
from repositories.contribution_repository import ContributionRepository
from repositories.frog_collection_repository import FrogCollectionRepository
from repositories.role_snapshot_repository import RoleSnapshotRepository
from services.profile_service import ProfileService
from services.birthday_service import BirthdayService
from domain.constants import ZODIAC_ROLE_IDS


def resolve_member_roles(member: discord.Member) -> MemberRoleContext:
    roles = [r for r in member.roles if not r.is_default()]
    role_ids = [r.id for r in roles]
    role_names = [r.name for r in roles]

    house_roles = [
        HOUSE_ROLE_IDS[r.id]
        for r in roles
        if r.id in HOUSE_ROLE_IDS
    ]

    current_house = house_roles[0] if len(house_roles) == 1 else None

    return MemberRoleContext(
        user_id=member.id,
        role_ids=role_ids,
        role_names=role_names,
        house_roles=house_roles,
        current_house=current_house,
        has_arena_role=ARENA_ROLE_ID in role_ids,
    )


def validate_house_context(role_ctx: MemberRoleContext) -> tuple[bool, str | None]:
    if len(role_ctx.house_roles) == 0:
        return False, "You need exactly one valid house role to use this command."
    if len(role_ctx.house_roles) > 1:
        return False, "You currently have multiple house roles. Please contact an admin."
    return True, None


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.birthday_service = BirthdayService()

    @app_commands.command(name="profile", description="Show a Hogwarts profile.")
    @app_commands.describe(member="The member whose profile you want to view")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        target = member or interaction.user

        if not isinstance(target, discord.Member):
            await interaction.response.send_message(
                "Invalid user.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(target)
        is_valid, error = validate_house_context(role_ctx)

        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            inventory_repo = InventoryRepository(conn)
            contribution_repo = ContributionRepository(conn)
            frog_collection_repo = FrogCollectionRepository(conn)
            role_snapshot_repo = RoleSnapshotRepository(conn)

            user_repo.ensure_user(target.id)

            role_snapshot_repo.replace_user_roles(
                target.id,
                [(role.id, role.name) for role in target.roles if not role.is_default()],
            )

            profile_service = ProfileService(
                user_repo=user_repo,
                inventory_repo=inventory_repo,
                contribution_repo=contribution_repo,
                frog_collection_repo=frog_collection_repo,
            )

            embeds, files = profile_service.build_profile_message(target, role_ctx)

        await interaction.response.send_message(
            embeds=embeds,
            files=files,
        )

    @app_commands.command(
        name="set_profile_bio",
        description="Set your profile bio (max 50 characters).",
    )
    @app_commands.describe(message="Your bio text")
    async def set_profile_bio(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        if len(message) > 50:
            await interaction.response.send_message(
                "Your bio can be at most 50 characters long.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)

        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        cleaned_message = message.strip()
        if not cleaned_message:
            cleaned_message = "n/a"

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            user_repo.ensure_user(interaction.user.id)
            user_repo.set_bio(interaction.user.id, cleaned_message)

        await interaction.response.send_message(
            f"Your profile bio has been updated to:\n**{cleaned_message}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_birthday",
        description="Set your birthday once.",
    )
    @app_commands.describe(
        day="Day of the month, e.g. 1 or 31",
        month="Month number, e.g. 4 for April",
    )
    async def set_birthday(
        self,
        interaction: discord.Interaction,
        day: app_commands.Range[int, 1, 31],
        month: app_commands.Range[int, 1, 12],
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        role_ctx = resolve_member_roles(interaction.user)
        is_valid, error = validate_house_context(role_ctx)
        if not is_valid:
            await interaction.response.send_message(error, ephemeral=True)
            return

        try:
            self.birthday_service.validate_birthday(day, month)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            user_repo.ensure_user(interaction.user.id)

            current_day, current_month = user_repo.get_birthday(interaction.user.id)
            if current_day is not None and current_month is not None:
                await interaction.response.send_message(
                    "Your birthday is already set. An admin must reset it before you can change it.",
                    ephemeral=True,
                )
                return

            user_repo.set_birthday(interaction.user.id, day, month)

        zodiac_sign = self.birthday_service.get_zodiac_sign(day, month)
        zodiac_role_id = ZODIAC_ROLE_IDS[zodiac_sign]

        # remove all zodiac roles first
        zodiac_role_ids = set(ZODIAC_ROLE_IDS.values())
        roles_to_remove = [role for role in interaction.user.roles if role.id in zodiac_role_ids]
        if roles_to_remove:
            try:
                await interaction.user.remove_roles(*roles_to_remove, reason="Birthday set - refreshing zodiac role")
            except discord.HTTPException:
                pass

        zodiac_role = interaction.guild.get_role(zodiac_role_id)
        if zodiac_role is not None:
            try:
                await interaction.user.add_roles(zodiac_role, reason="Birthday set - zodiac role assigned")
            except discord.HTTPException:
                pass

        birthday_text = self.birthday_service.format_birthday(day, month)
        zodiac_text = self.birthday_service.get_zodiac_display(zodiac_sign)

        await interaction.response.send_message(
            f"Your birthday has been set to **{birthday_text}**.\n"
            f"Your zodiac sign is **{zodiac_text}**.",
            ephemeral=True,
        )