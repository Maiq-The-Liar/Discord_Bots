import discord
from discord import app_commands
from discord.ext import commands

from domain.constants import ARROW_LEFT_EMOJI, ARROW_RIGHT_EMOJI, CLOSE_EMOJI


HELP_COLOR = 0x8B0000


HELP_TOPICS: dict[str, dict[str, object]] = {
    "getting_started": {
        "label": "Getting Started",
        "emoji": "🪄",
        "description": "A quick overview of the main things you can do.",
        "pages": [
            {
                "title": "🪄 Getting Started",
                "description": (
                    "Welcome to the Hogwarts Bot help menu. Pick a topic from the dropdown below, "
                    "then use the arrow buttons to move between pages."
                ),
                "fields": [
                    (
                        "First things to try",
                        "• Complete the Sorting/Housing Quiz when it is available.\n"
                        "• Use `/profile` to view your Hogwarts profile.\n"
                        "• Use `/shop` to spend Galleons on magical items.\n"
                        "• Use the public reaction-role menus to choose optional roles like identity, pings, colors, and Quidditch position.",
                    ),
                    (
                        "Your Hogwarts life",
                        "You can earn House Points, collect Chocolate Frog cards, discover a Patronus, join Quidditch, "
                        "support media posts, duel other members, and customize parts of your profile.",
                    ),
                ],
            },
            {
                "title": "🧭 What can I do?",
                "description": "The bot has several public activities for regular members.",
                "fields": [
                    (
                        "Activities",
                        "• Join quizzes and help your house in the House Cup.\n"
                        "• Buy items and collect Chocolate Frog cards.\n"
                        "• Discover and display your Patronus.\n"
                        "• Join Quidditch through your house and position role.\n"
                        "• Use reaction roles to personalize notifications and identity roles.",
                    ),
                    (
                        "Useful public commands",
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
        "description": "Profiles, bio, birthday, and personal role choices.",
        "pages": [
            {
                "title": "👤 Profile",
                "description": "Your profile is your public Hogwarts card.",
                "fields": [
                    (
                        "Viewing profiles",
                        "`/profile` — View your own profile.\n"
                        "`/profile member:@user` — View another member's profile.",
                    ),
                    (
                        "Customizing your profile",
                        "`/set_profile_bio message:<text>` — Set a short profile bio, up to 50 characters.\n"
                        "`/set_birthday day:<1-31> month:<1-12>` — Set your birthday once and receive your zodiac role when available.",
                    ),
                ],
            },
            {
                "title": "🏷️ Identity Roles",
                "description": "Identity and preference roles are chosen through the public reaction-role menus.",
                "fields": [
                    (
                        "Available role menus",
                        "Public menus include pronouns, gender identity, sexuality, relationship status, continent/location, "
                        "age range, DM status, ping roles, house colors, and Quidditch positions.",
                    ),
                    (
                        "How to change them",
                        "Go to the relevant role menu message and react/select the option you want. "
                        "For single-choice menus, picking a new option replaces your previous one. "
                        "For multi-choice menus, you may keep more than one role.",
                    ),
                ],
            },
        ],
    },
    "roles": {
        "label": "Reaction Roles",
        "emoji": "🎭",
        "description": "Self-assignable public roles and notification choices.",
        "pages": [
            {
                "title": "🎭 Reaction Roles",
                "description": "Reaction-role menus let you choose optional roles for yourself.",
                "fields": [
                    (
                        "Single-choice menus",
                        "Some menus allow one active choice at a time. These include pronouns, relationship status, "
                        "continent/location, age range, DM status, house color, and Quidditch position.",
                    ),
                    (
                        "Multi-choice menus",
                        "Some menus allow multiple choices. These include gender identity, sexuality, and ping roles.",
                    ),
                ],
            },
            {
                "title": "🔔 Pings, Colors & Quidditch Roles",
                "description": "These roles control notifications, appearance, and activity participation.",
                "fields": [
                    (
                        "Ping roles",
                        "Choose ping roles if you want notifications for things like duels, events, or chat revive pings.",
                    ),
                    (
                        "House colors",
                        "Choose one color variant for your house style.",
                    ),
                    (
                        "Quidditch positions",
                        "Choose one Quidditch position: Keeper, Seeker, Beater, or Chaser. "
                        "This tells your house which position you want to play.",
                    ),
                ],
            },
        ],
    },
    "economy_shop": {
        "label": "Economy & Shop",
        "emoji": "🛒",
        "description": "Galleons, shopping, items, and sending money.",
        "pages": [
            {
                "title": "🛒 Shop",
                "description": "Use `/shop` to browse magical items.",
                "fields": [
                    (
                        "How to shop",
                        "• Use the left/right buttons to browse items.\n"
                        "• Press the Galleons button to buy the item shown.\n"
                        "• Press the close button to close your shop menu.\n"
                        "• The shop shows the price, your balance, how many you own, and whether the item can be bought.",
                    ),
                    (
                        "Items you may see",
                        "• Chocolate Frogs — open them to collect cards.\n"
                        "• Patronus Spell Book — needed to discover or change your Patronus.\n"
                        "• S.P.E.W. Badge — a permanent collectible badge.",
                    ),
                ],
            },
            {
                "title": "💰 Galleons",
                "description": "Galleons are your magical money.",
                "fields": [
                    (
                        "Using Galleons",
                        "`/shop` — Buy items.\n"
                        "`/give_money member:@user amount:<number>` — Give some of your own Galleons to another member.",
                    ),
                    (
                        "Earning Galleons",
                        "You can earn Galleons from activities such as quizzes, duels, House Cup rewards, and other gameplay rewards.",
                    ),
                ],
            },
        ],
    },
    "collectibles_magic": {
        "label": "Collectibles & Magic",
        "emoji": "🍫",
        "description": "Chocolate Frog cards, albums, trading, and Patronus.",
        "pages": [
            {
                "title": "🍫 Chocolate Frogs",
                "description": "Collect Chocolate Frog cards and complete your album.",
                "fields": [
                    (
                        "Commands",
                        "`/open_chocolate_frog` — Open one Chocolate Frog you own and reveal a card.\n"
                        "`/frog_album` — Browse your own collection.\n"
                        "`/frog_album member:@user` — Browse another member's collection.\n"
                        "`/give_card member:@user card_id:<id>` — Give one of your cards to another member.",
                    ),
                    (
                        "Album browsing",
                        "The album has page buttons so you can flip through your cards and check your collection progress.",
                    ),
                ],
            },
            {
                "title": "🦌 Patronus",
                "description": "Discover and show your Patronus.",
                "fields": [
                    (
                        "Commands",
                        "`/discoverpatronus` — Use a Patronus Spell Book to discover or change your Patronus.\n"
                        "`/patronus` — Show your current Patronus.",
                    ),
                    (
                        "Item needed",
                        "You need a Patronus Spell Book from `/shop` before you can use `/discoverpatronus` successfully.",
                    ),
                ],
            },
        ],
    },
    "house_cup_quizzes": {
        "label": "House Cup & Quizzes",
        "emoji": "🏆",
        "description": "House Points, quizzes, rewards, and school progress.",
        "pages": [
            {
                "title": "🏆 House Cup",
                "description": "Earn points for your house through server activities.",
                "fields": [
                    (
                        "How points work",
                        "House Points are tracked for the House Cup. Your activity can help your house total and appear on your profile.",
                    ),
                    (
                        "Rewards",
                        "House Cup results can include Galleon rewards for top players and winning houses.",
                    ),
                ],
            },
            {
                "title": "🧠 Quizzes & School Progress",
                "description": "Quiz questions appear in quiz channels when a quiz is active.",
                "fields": [
                    (
                        "Quiz participation",
                        "Answer in the quiz channel. Correct answers receive a ✅ reaction, award **2 House Points**, "
                        "award **5 Galleons**, and move the quiz forward.",
                    ),
                    (
                        "School years",
                        "Your profile can show your school-year progress as you take part in activities over time.",
                    ),
                ],
            },
        ],
    },
    "duels_media": {
        "label": "Duels & Media",
        "emoji": "⚔️",
        "description": "Dueling Club, answering questions, and supporting media posts.",
        "pages": [
            {
                "title": "⚔️ Dueling Club",
                "description": "Dueling Club is played from the public duel message.",
                "fields": [
                    (
                        "Joining a duel",
                        "• Press **Start Duel** to open a lobby.\n"
                        "• Press **Join Game** to join.\n"
                        "• Press **Leave** if you change your mind before the duel starts.",
                    ),
                    (
                        "Playing",
                        "When the duel begins, answer the questions in the duel channel. Scores and rewards are handled automatically.",
                    ),
                ],
            },
            {
                "title": "📸 Media Support",
                "description": "Support other members' media posts with hearts.",
                "fields": [
                    (
                        "Posting and voting",
                        "Upload supported media in a media channel, then other members can react with ❤️ to support it. "
                        "You cannot support your own post.",
                    ),
                    (
                        "Voting limit",
                        "Each user can support up to **3** media posts per hour.",
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
        "description": "Monthly cup, positions, fixtures, betting, cheering, and strategy.",
        "pages": [
            {
                "title": "🧹 Monthly Quidditch Cup",
                "description": "Quidditch is a monthly house competition.",
                "fields": [
                    (
                        "Cup format",
                        "Each monthly Quidditch Cup includes **6 games per house**, followed by a **Bronze Medal Game** "
                        "and the **Championship Final**.",
                    ),
                    (
                        "Taking part",
                        "Choose a Quidditch position role from the reaction-role menu: Keeper, Seeker, Beater, or Chaser. "
                        "Your house and position show where you want to play.",
                    ),
                ],
            },
            {
                "title": "📅 Fixtures & Match Info",
                "description": "Quidditch match messages show what is happening and when.",
                "fields": [
                    (
                        "Timetable",
                        "Check the Quidditch scoreboard, previews, and match posts for upcoming fixtures, start times, scores, and results.",
                    ),
                    (
                        "Match posts",
                        "Before and during a match, the match embed can show the teams, score, phase of play, betting status, and available interactions.",
                    ),
                ],
            },
            {
                "title": "🎲 Betting & Cheering",
                "description": "You can support a match even when you are not playing.",
                "fields": [
                    (
                        "Betting",
                        "Before a match starts, the betting preview lets you pick a house and enter a Galleon stake. "
                        "Each user can place one bet per fixture, and betting closes before the match begins.",
                    ),
                    (
                        "Cheering",
                        "During live matches, use the cheer buttons on the match message to support a house.",
                    ),
                ],
            },
            {
                "title": "📋 Strategy Insight",
                "description": "House strategy gives members a way to influence their house's approach.",
                "fields": [
                    (
                        "Strategy voting",
                        "When a strategy prompt is active for your house, you can vote for options such as Chaser Rush, "
                        "Seeker Hunt, Bludger Storm, Close Formation, or Keeper Lock.",
                    ),
                    (
                        "Contingency voting",
                        "Your house may also choose a backup plan for the match. These votes help decide how your house approaches key moments.",
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
