import discord
from discord import app_commands
from discord.ext import commands

from domain.constants import ARROW_LEFT_EMOJI, ARROW_RIGHT_EMOJI, CLOSE_EMOJI


HELP_COLOR = 0x8B0000


HELP_TOPICS: dict[str, dict[str, object]] = {
    "getting_started": {
        "label": "Getting Started",
        "emoji": "🪄",
        "description": "Sorting, basic progress, and the best first commands to use.",
        "pages": [
            {
                "title": "🪄 Getting Started",
                "description": (
                    "Welcome to the Hogwarts Bot help menu. Use the dropdown below to choose a topic, "
                    "then use the arrow buttons to flip through that topic's pages."
                ),
                "fields": [
                    (
                        "First steps",
                        "• Complete the Sorting/Housing Quiz when the server presents it.\n"
                        "• Use `/profile` to see your Hogwarts profile.\n"
                        "• Use `/shop` to spend Galleons on collectibles and consumables.\n"
                        "• Use reaction-role menus to set optional identity, ping, color, and Quidditch roles.",
                    ),
                    (
                        "Progress basics",
                        "Your profile can show your house, school year progress, Galleons, Chocolate Frog progress, "
                        "Patronus, House Cup contributions, Quidditch progress, and selected profile details.",
                    ),
                ],
            },
            {
                "title": "🧭 What can I do?",
                "description": "The bot is split into several end-user systems.",
                "fields": [
                    (
                        "Main activities",
                        "• Earn House Points in quizzes, duels, media support, and other activities.\n"
                        "• Collect Chocolate Frog cards.\n"
                        "• Discover and show your Patronus.\n"
                        "• Join Quidditch as a player, strategist, supporter, or bettor.\n"
                        "• Personalize your profile and self-assign public roles.",
                    ),
                    (
                        "Useful commands",
                        "`/help`, `/profile`, `/shop`, `/set_profile_bio`, `/set_birthday`, `/give_money`, "
                        "`/open_chocolate_frog`, `/frog_album`, `/give_card`, `/patronus`, `/discoverpatronus`",
                    ),
                ],
            },
        ],
    },
    "profile_identity": {
        "label": "Profile & Identity",
        "emoji": "👤",
        "description": "Profiles, bio, birthday, pronouns, age, continent, and role menus.",
        "pages": [
            {
                "title": "👤 Profile Commands",
                "description": "Use these commands to view and customize your Hogwarts identity.",
                "fields": [
                    (
                        "Profile",
                        "`/profile` — View your own profile.\n"
                        "`/profile member:@user` — View another member's profile.\n"
                        "`/set_profile_bio message:<text>` — Set your profile bio, up to 50 characters.",
                    ),
                    (
                        "Birthday",
                        "`/set_birthday day:<1-31> month:<1-12>` — Set your birthday once. "
                        "The bot saves it and assigns your zodiac role when available.",
                    ),
                ],
            },
            {
                "title": "🏷️ Identity Roles",
                "description": "Some identity roles can be changed with commands and/or reaction-role menus.",
                "fields": [
                    (
                        "Command-based role updates",
                        "`/set_pronouns` — Choose your pronoun role.\n"
                        "`/set_age` — Choose your age range role.\n"
                        "`/set_continent` — Choose your continent/location role.",
                    ),
                    (
                        "Reaction-role menus",
                        "Available public menus include pronouns, gender identity, sexuality, relationship status, "
                        "continent/location, age range, DM status, ping roles, house colors, and Quidditch positions.",
                    ),
                ],
            },
        ],
    },
    "roles": {
        "label": "Reaction Roles",
        "emoji": "🎭",
        "description": "Public self-assignable role menus and how they behave.",
        "pages": [
            {
                "title": "🎭 Reaction Roles",
                "description": "React to the role-menu messages to add or remove public roles from yourself.",
                "fields": [
                    (
                        "Single-choice menus",
                        "Some menus allow only one active role at a time. Choosing a new option replaces your old one. "
                        "These include pronouns, relationship status, continent/location, age range, DM status, "
                        "house color, and Quidditch position.",
                    ),
                    (
                        "Multi-choice menus",
                        "Some menus allow multiple roles at once. These include gender identity, sexuality, and ping roles.",
                    ),
                ],
            },
            {
                "title": "🔔 Ping, Color & Quidditch Roles",
                "description": "These role menus affect notifications, visuals, and Quidditch participation.",
                "fields": [
                    (
                        "Ping roles",
                        "Use ping roles to opt into notifications such as Duel pings, Event pings, and Chat Revive pings.",
                    ),
                    (
                        "House colors",
                        "Each house has its own color-role menu. Pick one color variant for your house style.",
                    ),
                    (
                        "Quidditch positions",
                        "Choose one Quidditch position role: Keeper, Seeker, Beater, or Chaser. "
                        "This helps the Quidditch system build lineups for your house.",
                    ),
                ],
            },
        ],
    },
    "economy_shop": {
        "label": "Economy & Shop",
        "emoji": "🛒",
        "description": "Galleons, shop browsing, buying items, and paying other users.",
        "pages": [
            {
                "title": "🛒 Shop",
                "description": "Use `/shop` to open your personal shop session.",
                "fields": [
                    (
                        "How the shop works",
                        "• Use the left/right buttons to browse shop items.\n"
                        "• Press the Galleons button to buy the current item.\n"
                        "• Press the close button to end the shop session.\n"
                        "• The shop shows item price, owned amount, item type, balance, and status.",
                    ),
                    (
                        "Current item types",
                        "• Chocolate Frogs — consumable collectible packs.\n"
                        "• Patronus Spell Book — consumable item for Patronus discovery/change.\n"
                        "• S.P.E.W. Badge — permanent collectible badge.",
                    ),
                ],
            },
            {
                "title": "💰 Galleons",
                "description": "Galleons are the bot's money system.",
                "fields": [
                    (
                        "Spending and sharing",
                        "`/shop` — Spend Galleons on items.\n"
                        "`/give_money member:@user amount:<number>` — Give your own Galleons to another member.",
                    ),
                    (
                        "Earning",
                        "You can earn Galleons through user-facing activities such as quiz rewards, duel rewards, "
                        "House Cup placement rewards, and other gameplay systems when enabled.",
                    ),
                ],
            },
        ],
    },
    "collectibles_magic": {
        "label": "Collectibles & Magic",
        "emoji": "🍫",
        "description": "Chocolate Frog cards, albums, trading, and Patronus commands.",
        "pages": [
            {
                "title": "🍫 Chocolate Frogs",
                "description": "Collect Chocolate Frog cards and browse your album.",
                "fields": [
                    (
                        "Commands",
                        "`/open_chocolate_frog` — Open one owned Chocolate Frog and reveal a card.\n"
                        "`/frog_album` — Browse your own collection.\n"
                        "`/frog_album member:@user` — Browse another member's collection.\n"
                        "`/give_card member:@user card_id:<id>` — Give one owned card to another member.",
                    ),
                    (
                        "Album browsing",
                        "The album has its own page buttons so you can flip through collected cards and see duplicates/progress.",
                    ),
                ],
            },
            {
                "title": "🦌 Patronus",
                "description": "Discover and display your Patronus.",
                "fields": [
                    (
                        "Commands",
                        "`/discoverpatronus` — Use a Patronus Spell Book to discover or change your Patronus.\n"
                        "`/patronus` — Show your current Patronus.",
                    ),
                    (
                        "Item requirement",
                        "You need a Patronus Spell Book from `/shop` before `/discoverpatronus` can be used successfully.",
                    ),
                ],
            },
        ],
    },
    "house_cup_quizzes": {
        "label": "House Cup & Quizzes",
        "emoji": "🏆",
        "description": "House Points, quiz rewards, school years, and monthly competition.",
        "pages": [
            {
                "title": "🏆 House Cup",
                "description": "Earn points for your house through server activities.",
                "fields": [
                    (
                        "How points work",
                        "House Points are tracked monthly. Your activity can contribute to your house total and your own profile stats.",
                    ),
                    (
                        "Rewards",
                        "At the end of a House Cup period, the system can announce results and reward top players with Galleons.",
                    ),
                ],
            },
            {
                "title": "🧠 Casual Quiz & School Progress",
                "description": "Quiz questions appear in configured quiz channels when active.",
                "fields": [
                    (
                        "Quiz participation",
                        "Reply in the quiz channel with your answer. Correct answers receive a ✅ reaction, "
                        "award **2 House Points**, award **5 Galleons**, and trigger the next question.",
                    ),
                    (
                        "School years and XP",
                        "The leveling system tracks school-year progress over time and can display that progress on your profile.",
                    ),
                ],
            },
        ],
    },
    "duels_media": {
        "label": "Duels & Media",
        "emoji": "⚔️",
        "description": "Dueling Club buttons, answer flow, and media support voting.",
        "pages": [
            {
                "title": "⚔️ Dueling Club",
                "description": "Duels are started from the public duel message in a duel channel.",
                "fields": [
                    (
                        "Joining a duel",
                        "• Press **Start Duel** to open a lobby.\n"
                        "• Press **Join Game** to join the lobby.\n"
                        "• Press **Leave** if you change your mind before it starts.",
                    ),
                    (
                        "Playing",
                        "When the duel starts, answer the questions in the duel channel. Scores and rewards are handled automatically.",
                    ),
                ],
            },
            {
                "title": "📸 Media Support",
                "description": "Media support works in enabled media channels.",
                "fields": [
                    (
                        "Posting media",
                        "Upload supported media in a media channel. The bot adds a ❤️ reaction and tracks the post for voting.",
                    ),
                    (
                        "Voting rules",
                        "React with ❤️ to support someone else's media. You cannot support your own post, "
                        "and each user can support up to **3** media posts per hour.",
                    ),
                    (
                        "Rewards",
                        "When voting closes, the author receives House Points based on valid support votes.",
                    ),
                ],
            },
        ],
    },
    "quidditch": {
        "label": "Quidditch",
        "emoji": "🧹",
        "description": "Position roles, match timetable, betting, cheering, and strategy insight.",
        "pages": [
            {
                "title": "🧹 Quidditch Overview",
                "description": "Quidditch is a house-vs-house system with scheduled matches, player lineups, betting, cheering, and strategy votes.",
                "fields": [
                    (
                        "Role selection",
                        "Use the Quidditch Position reaction-role menu to pick one role: Keeper, Seeker, Beater, or Chaser. "
                        "Your house and position help the bot choose match lineups.",
                    ),
                    (
                        "Timetable info",
                        "Official matches are scheduled by the bot when the Quidditch loop is active. "
                        "The scoreboard and match/betting messages show upcoming fixtures, kickoff timing, and match state.",
                    ),
                ],
            },
            {
                "title": "🎲 Quidditch Betting & Cheering",
                "description": "Users can interact with match preview and live-match embeds.",
                "fields": [
                    (
                        "Betting",
                        "Before a match, the betting preview lets you pick a house and enter a Galleon stake. "
                        "Each user can place one bet per fixture, and betting closes before kickoff.",
                    ),
                    (
                        "Cheering",
                        "During live matches, use the cheer buttons to support a house. "
                        "Cheering is handled through the live match message, not a slash command.",
                    ),
                ],
            },
            {
                "title": "📋 Quidditch Strategy Insight",
                "description": "House strategy channels let members influence their house's match plan.",
                "fields": [
                    (
                        "Strategy voting",
                        "House members can vote for a strategy such as Chaser Rush, Seeker Hunt, Bludger Storm, "
                        "Close Formation, or Keeper Lock when a strategy prompt is active.",
                    ),
                    (
                        "Contingency voting",
                        "House members can also vote for a contingency plan. These choices help shape the simulated match flow.",
                    ),
                    (
                        "Visibility",
                        "Strategy prompts are intended for the matching house's strategy channel, so only relevant house members should vote there.",
                    ),
                ],
            },
        ],
    },
}


class HelpTopicSelect(discord.ui.Select):
    def __init__(self, view: "HelpView") -> None:
        options = [
            discord.SelectOption(
                label=str(topic["label"]),
                value=key,
                description=str(topic["description"]),
                emoji=str(topic["emoji"]),
            )
            for key, topic in HELP_TOPICS.items()
        ]
        super().__init__(
            placeholder="Choose a help topic...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )
        self.help_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        self.help_view.current_topic_key = self.values[0]
        self.help_view.current_page_index = 0
        await self.help_view.refresh(interaction)


class HelpView(discord.ui.View):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.current_topic_key = "getting_started"
        self.current_page_index = 0
        self.add_item(HelpTopicSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This help menu belongs to someone else. Use `/help` to open your own.",
                ephemeral=True,
            )
            return False
        return True

    @property
    def current_pages(self) -> list[dict[str, object]]:
        topic = HELP_TOPICS[self.current_topic_key]
        return list(topic["pages"])  # type: ignore[arg-type]

    def build_embed(self) -> discord.Embed:
        topic = HELP_TOPICS[self.current_topic_key]
        pages = self.current_pages
        page = pages[self.current_page_index]

        embed = discord.Embed(
            title=str(page["title"]),
            description=str(page["description"]),
            color=HELP_COLOR,
        )

        for name, value in page.get("fields", []):  # type: ignore[union-attr]
            embed.add_field(name=str(name), value=str(value), inline=False)

        embed.set_footer(
            text=(
                f"{topic['label']} • Page {self.current_page_index + 1}/{len(pages)} • "
                "Use the dropdown to change topic."
            )
        )
        return embed

    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(
        emoji=ARROW_LEFT_EMOJI,
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def previous_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_page_index = (self.current_page_index - 1) % len(self.current_pages)
        await self.refresh(interaction)

    @discord.ui.button(
        emoji=ARROW_RIGHT_EMOJI,
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_page_index = (self.current_page_index + 1) % len(self.current_pages)
        await self.refresh(interaction)

    @discord.ui.button(
        emoji=CLOSE_EMOJI,
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def close_help(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="Help menu closed.",
            embed=None,
            view=self,
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Open the Hogwarts Bot end-user help menu.",
    )
    async def help(self, interaction: discord.Interaction) -> None:
        view = HelpView(owner_id=interaction.user.id)
        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )
