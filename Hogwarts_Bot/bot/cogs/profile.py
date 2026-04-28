import discord
from discord import app_commands
from discord.ext import commands

from db.database import Database
from domain.constants import ARENA_ROLE_ID
from domain.role_registry import (
    AGE_CHOICE_TO_ROLE_KEY,
    CONTINENT_CHOICE_TO_ROLE_KEY,
    HOUSE_NAMES,
    PRONOUN_CHOICE_TO_ROLE_KEY,
    ROLE_GROUP_AGES,
    ROLE_GROUP_CONTINENTS,
    ROLE_GROUP_PRONOUNS,
    ROLE_GROUP_ZODIAC,
    ROLE_KEY_BIRTHDAY,
    role_names_for_group,
    zodiac_role_key_for_sign,
)
from repositories.guild_role_repository import GuildRoleRepository
from repositories.quidditch_progress_repository import QuidditchProgressRepository
from services.role_service import RoleService
from domain.role_context import MemberRoleContext
from repositories.user_repository import UserRepository
from repositories.inventory_repository import InventoryRepository
from repositories.contribution_repository import ContributionRepository
from repositories.frog_collection_repository import FrogCollectionRepository
from repositories.role_snapshot_repository import RoleSnapshotRepository
from services.profile_service import ProfileService
from services.birthday_service import BirthdayService
from services.economy_service import EconomyService


def resolve_member_roles(member: discord.Member) -> MemberRoleContext:
    roles = [r for r in member.roles if not r.is_default()]
    role_ids = [r.id for r in roles]
    role_names = [r.name for r in roles]

    house_name_set = {house_name.lower() for house_name in HOUSE_NAMES}
    house_roles = [
        r.name
        for r in roles
        if r.name.strip().lower() in house_name_set
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


    @app_commands.command(name="give_money", description="Give some of your Galleons to another user.")
    @app_commands.describe(member="The member you want to pay", amount="Amount of Galleons to give")
    async def give_money(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1],
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside the server.",
                ephemeral=True,
            )
            return

        if member.bot:
            await interaction.response.send_message(
                "You cannot give money to bots.",
                ephemeral=True,
            )
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot give money to yourself.",
                ephemeral=True,
            )
            return

        with self.database.connect() as conn:
            user_repo = UserRepository(conn)
            economy_service = EconomyService(user_repo)

            user_repo.ensure_user(interaction.user.id)
            user_repo.ensure_user(member.id)

            sender_before = user_repo.get_user(interaction.user.id)
            if int(sender_before["galleons_balance"]) < amount:
                await interaction.response.send_message(
                    f"You only have **{sender_before['galleons_balance']}** Galleons.",
                    ephemeral=True,
                )
                return

            success = economy_service.transfer_money(interaction.user.id, member.id, amount)
            if not success:
                await interaction.response.send_message(
                    "Transfer failed because you do not have enough Galleons.",
                    ephemeral=True,
                )
                return

            sender_after = user_repo.get_user(interaction.user.id)
            recipient_after = user_repo.get_user(member.id)

        await interaction.response.send_message(
            f"{interaction.user.mention} gave **{amount}** Galleons to {member.mention}.\n"
            f"Your new balance: **{sender_after['galleons_balance']}** Galleons.\n"
            f"{member.display_name}'s new balance: **{recipient_after['galleons_balance']}** Galleons."
        )


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
            role_repo = GuildRoleRepository(conn)
            quidditch_progress_repo = QuidditchProgressRepository(conn)

            user_repo.ensure_user(target.id)
            quidditch_progress_repo.ensure_user_positions(target.id)

            role_snapshot_repo.replace_user_roles(
                target.id,
                [(role.id, role.name) for role in target.roles if not role.is_default()],
            )

            role_service = RoleService(role_repo)

            profile_service = ProfileService(
                user_repo=user_repo,
                inventory_repo=inventory_repo,
                contribution_repo=contribution_repo,
                frog_collection_repo=frog_collection_repo,
                role_service=role_service,
                quidditch_progress_repo=quidditch_progress_repo,
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
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)

            user_repo.ensure_user(interaction.user.id)

            current_day, current_month = user_repo.get_birthday(interaction.user.id)
            if current_day is not None and current_month is not None:
                await interaction.response.send_message(
                    "Your birthday is already set. An admin must reset it before you can change it.",
                    ephemeral=True,
                )
                return

            user_repo.set_birthday(interaction.user.id, day, month)
            zodiac_role = role_service.get_zodiac_role(
                interaction.guild,
                self.birthday_service.get_zodiac_sign(day, month),
            )

        zodiac_role_names = role_names_for_group(ROLE_GROUP_ZODIAC)
        roles_to_remove = [
            role for role in interaction.user.roles
            if role.name in zodiac_role_names
        ]

        if roles_to_remove:
            try:
                await interaction.user.remove_roles(
                    *roles_to_remove,
                    reason="Birthday set - refreshing zodiac role",
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "Your birthday was saved, but I could not remove your old zodiac role.",
                    ephemeral=True,
                )
                return

        if zodiac_role is not None:
            try:
                await interaction.user.add_roles(
                    zodiac_role,
                    reason="Birthday set - zodiac role assigned",
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "Your birthday was saved, but I could not assign your zodiac role.",
                    ephemeral=True,
                )
                return

        zodiac_sign = self.birthday_service.get_zodiac_sign(day, month)
        await interaction.response.send_message(
            f"Your birthday has been set to **{day:02d}/{month:02d}**.\n"
            f"Your zodiac sign is **{zodiac_sign}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_pronouns",
        description="Set your pronoun role.",
    )
    @app_commands.describe(pronouns="Choose your pronouns")
    @app_commands.choices(
        pronouns=[
            app_commands.Choice(name="She/Her", value="she_her"),
            app_commands.Choice(name="She/They", value="she_they"),
            app_commands.Choice(name="He/Him", value="he_him"),
            app_commands.Choice(name="He/They", value="he_they"),
            app_commands.Choice(name="They/Them", value="they_them"),
            app_commands.Choice(name="Ask Pronouns", value="ask_pronouns"),
        ]
    )
    async def set_pronouns(
        self,
        interaction: discord.Interaction,
        pronouns: app_commands.Choice[str],
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

        with self.database.connect() as conn:
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)
            new_role = role_service.get_role(
                interaction.guild,
                PRONOUN_CHOICE_TO_ROLE_KEY[pronouns.value],
            )

        if new_role is None:
            await interaction.response.send_message(
                "That pronoun role could not be found. Run `/update_roles` first.",
                ephemeral=True,
            )
            return

        pronoun_role_names = role_names_for_group(ROLE_GROUP_PRONOUNS)
        roles_to_remove = [
            role for role in interaction.user.roles
            if role.name in pronoun_role_names
        ]

        if roles_to_remove:
            try:
                await interaction.user.remove_roles(
                    *roles_to_remove,
                    reason="Updating pronoun role",
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "I could not remove your current pronoun role.",
                    ephemeral=True,
                )
                return

        try:
            await interaction.user.add_roles(
                new_role,
                reason="Pronoun role selected by user",
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "I could not assign your new pronoun role.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Your pronouns have been updated to **{new_role.name}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_age",
        description="Set your age range role.",
    )
    @app_commands.describe(age_range="Choose your age range")
    @app_commands.choices(
        age_range=[
            app_commands.Choice(name="Below 18", value="below_18"),
            app_commands.Choice(name="18-25", value="21_25"),
            app_commands.Choice(name="26-30", value="26_30"),
            app_commands.Choice(name="31-35", value="31_35"),
            app_commands.Choice(name="36-40", value="36_40"),
            app_commands.Choice(name="41-45", value="41_45"),
            app_commands.Choice(name="46+", value="46_plus"),
        ]
    )
    async def set_age(
        self,
        interaction: discord.Interaction,
        age_range: app_commands.Choice[str],
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

        with self.database.connect() as conn:
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)
            new_role = role_service.get_role(
                interaction.guild,
                AGE_CHOICE_TO_ROLE_KEY[age_range.value],
            )

        if new_role is None:
            await interaction.response.send_message(
                "That age role could not be found. Run `/update_roles` first.",
                ephemeral=True,
            )
            return

        age_role_names = role_names_for_group(ROLE_GROUP_AGES)
        roles_to_remove = [
            role for role in interaction.user.roles
            if role.name in age_role_names
        ]

        if roles_to_remove:
            try:
                await interaction.user.remove_roles(
                    *roles_to_remove,
                    reason="Updating age role",
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "I could not remove your current age role.",
                    ephemeral=True,
                )
                return

        try:
            await interaction.user.add_roles(
                new_role,
                reason="Age role selected by user",
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "I could not assign your new age role.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Your age range has been updated to **{new_role.name}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_continent",
        description="Set your continent role.",
    )
    @app_commands.describe(continent="Choose your continent")
    @app_commands.choices(
        continent=[
            app_commands.Choice(name="Africa", value="africa"),
            app_commands.Choice(name="Antarctica", value="antarctica"),
            app_commands.Choice(name="Asia", value="asia"),
            app_commands.Choice(name="Australia & Oceania", value="australia_oceania"),
            app_commands.Choice(name="Europe", value="europe"),
            app_commands.Choice(name="North America", value="north_america"),
            app_commands.Choice(name="South America", value="south_america"),
        ]
    )
    async def set_continent(
        self,
        interaction: discord.Interaction,
        continent: app_commands.Choice[str],
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

        with self.database.connect() as conn:
            role_repo = GuildRoleRepository(conn)
            role_service = RoleService(role_repo)
            new_role = role_service.get_role(
                interaction.guild,
                CONTINENT_CHOICE_TO_ROLE_KEY[continent.value],
            )

        if new_role is None:
            await interaction.response.send_message(
                "That continent role could not be found. Run `/update_roles` first.",
                ephemeral=True,
            )
            return

        continent_role_names = role_names_for_group(ROLE_GROUP_CONTINENTS)
        roles_to_remove = [
            role for role in interaction.user.roles
            if role.name in continent_role_names
        ]

        if roles_to_remove:
            try:
                await interaction.user.remove_roles(
                    *roles_to_remove,
                    reason="Updating continent role",
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "I could not remove your current continent role.",
                    ephemeral=True,
                )
                return

        try:
            await interaction.user.add_roles(
                new_role,
                reason="Continent role selected by user",
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "I could not assign your new continent role.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Your continent has been updated to **{new_role.name}**.",
            ephemeral=True,
        )