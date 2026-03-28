import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

DATA_DIR = Path(__file__).parent
INVENTORY_FILE = DATA_DIR / "inventory.json"
FLAVORS_FILE = DATA_DIR / "flavors.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
TASTED_FLAVOURS_FILE = DATA_DIR / "tasted_flavours.json"

EVENT_TITLE = "\"Would Master kindly give Dobby another sock?\""
EVENT_DESCRIPTION = (
    "Dobby has appeared and is in desperate need of some socks.\n"
    "Each person may click exactly one button. Make sure you give him his favourite one...!"
)

EVENT_GIF_URLS = [
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Dobby_bed.gif?raw=true"
]

BEAN_IMAGE_URLS = [
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean1_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean2_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean3_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean4_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean5_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean6_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean7_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean8_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean9_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean10_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean11_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean12_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean13_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean14_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean15_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean16_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Bean17_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Birthday_Cake_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Caramel_Corn_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Chocolate_Pudding_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Coconut_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Licorice_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Plum_cleanup.png?raw=true",
    "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Beans/Strawberry_Jam_cleanup.png?raw=true",
]

ALL_FLAVOURS = [
    "Burger","Cheeseburger","Double Bacon Burger","Burnt Burger","Frozen Burger","Spicy Burger","Radioactive Burger","Cursed Burger","Quantum Burger","Glowing Burger",
    "Pizza","Pepperoni Pizza","Pineapple Pizza","Cold Pizza","Greasy Pizza","Frozen Pizza","Exploding Pizza","Cosmic Pizza","Void Pizza","Haunted Pizza",
    "Caramel","Salted Caramel","Burnt Caramel","Liquid Caramel","Caramel Explosion","Sticky Caramel","Molten Caramel","Ancient Caramel","Cursed Caramel",
    "Chocolate","Dark Chocolate","White Chocolate","Melted Chocolate","Burnt Chocolate","Frozen Chocolate","Cosmic Chocolate","Haunted Chocolate","Radioactive Chocolate",
    "Strawberry","Rotten Strawberry","Chocolate Covered Strawberry","Frozen Strawberry","Mutant Strawberry","Exploding Strawberry","Cursed Strawberry",
    "Vanilla","French Vanilla","Artificial Vanilla","Burnt Vanilla","Frozen Vanilla","Ancient Vanilla","Void Vanilla",
    "Kimchi","Fermented Kimchi Explosion","Spicy Kimchi","Ultra Spicy Kimchi","Rotten Kimchi","Cosmic Kimchi","Glowing Kimchi",
    "Sushi","Old Sushi","Gas Station Sushi","Frozen Sushi","Radioactive Sushi","Cursed Sushi","Alien Sushi",
    "Fries","Soggy Fries","Overcooked Fries","Radioactive Fries","Frozen Fries","Exploding Fries","Cosmic Fries",
    "Cheesecake","Strawberry Cheesecake","Moldy Cheesecake","Quantum Cheesecake","Frozen Cheesecake","Exploding Cheesecake",
    "Pancakes","Burnt Pancakes","Syrupy Pancakes","Mystery Pancakes","Frozen Pancakes","Exploding Pancakes",
    "Hotdog","Street Hotdog","Cold Hotdog","Exploding Hotdog","Radioactive Hotdog","Alien Hotdog",
    "Taco","Spicy Taco","Falling Apart Taco","Ancient Taco","Exploding Taco","Cursed Taco",
    "Spaghetti","Overcooked Spaghetti","Dry Spaghetti","Glowing Spaghetti","Radioactive Spaghetti","Alien Spaghetti",
    "Lasagna","Grandma's Lasagna","Frozen Lasagna","Suspicious Lasagna","Burnt Lasagna","Cosmic Lasagna",
    "Ice Cream","Melted Ice Cream","Freezer Burn Ice Cream","Haunted Ice Cream","Alien Ice Cream","Exploding Ice Cream",
    "Donut","Glazed Donut","Stale Donut","Alien Donut","Cosmic Donut","Exploding Donut",
    "Popcorn","Burnt Popcorn","Butter Explosion Popcorn","Cosmic Popcorn","Exploding Popcorn","Radioactive Popcorn",
    "Garlic Bread","Extra Garlic Bread","Charred Garlic Bread","Eternal Garlic Bread","Cursed Garlic Bread","Glowing Garlic Bread",
    "Ramen","Instant Ramen","Overcooked Ramen","Time Traveling Ramen","Exploding Ramen","Cursed Ramen",
    "Fried Chicken","Crispy Fried Chicken","Greasy Fried Chicken","Galaxy Fried Chicken","Radioactive Chicken","Exploding Chicken",
    "Steak","Rare Steak","Burnt Steak","Void Steak","Cosmic Steak","Exploding Steak",
    "Apple Pie","Grandma Apple Pie","Soggy Apple Pie","Parallel Apple Pie","Exploding Apple Pie","Cursed Apple Pie",
    "Freshly Mown Grass","Wet Grass","Dry Grass","Morning Dew Grass","Glowing Grass","Cursed Grass",
    "Rainwater","Dirty Rainwater","Acid Rainwater","Radioactive Rainwater","Frozen Rainwater",
    "Forest Moss","Damp Moss","Ancient Moss","Glowing Moss","Alien Moss",
    "Ocean Breeze","Salty Ocean Water","Fishy Ocean Breeze","Radioactive Ocean Breeze",
    "Wet Dirt","Mud","Swamp Mud","Cursed Mud","Glowing Mud",
    "Tree Bark","Chewed Tree Bark","Old Tree Bark","Ancient Bark",
    "Flower Petal","Rotten Flower Petal","Perfumed Flower Petal","Glowing Petal",
    "Autumn Leaves","Crunchy Leaves","Rotten Leaves","Cursed Leaves",
    "Mountain Air","Thin Mountain Air","Cold Mountain Air","Frozen Air",
    "Pine Needle","Sharp Pine Needle","Sap Covered Pine Needle","Radioactive Needle",
    "Rotten Egg","Exploded Rotten Egg","Burnt Rotten Egg","Nuclear Rotten Egg",
    "Vomit","Chunky Vomit","Warm Vomit","Radioactive Vomit","Exploding Vomit",
    "Poop","Dry Poop","Suspicious Poop","Quantum Poop","Radioactive Poop",
    "Explosive Diarrhea","Nuclear Diarrhea","Unstoppable Diarrhea","Cosmic Diarrhea",
    "Sour Milk","Chunky Milk","Expired Milk","Exploding Milk",
    "Moldy Bread","Green Mold Bread","Fuzzy Bread","Radioactive Bread",
    "Expired Yogurt","Lumpy Yogurt","Sour Yogurt","Dimension Tear Yogurt",
    "Old Cheese","Super Stinky Cheese","Melted Old Cheese","Exploding Cheese",
    "Garbage Juice","Dumpster Liquid","Mystery Garbage Soup","Blessed Garbage Juice",
    "Fermented Fish Disaster","Rotten Fish","Fish Juice","Exploding Fish Juice",
    "Toothpaste","Mint Toothpaste","Extra Strong Toothpaste","Exploding Toothpaste",
    "Soap","Lavender Soap","Bitter Soap","Time Loop Soap",
    "Shampoo","Cheap Shampoo","Hotel Shampoo","Alien Shampoo",
    "Plastic","Burnt Plastic","Melted Plastic","Void Plastic",
    "Rubber","Burnt Rubber","Tire Rubber","Cosmic Rubber",
    "Burnt Hair","Hair Clump","Singed Hair","Exploding Hair",
    "Candle Wax","Hot Wax","Scented Wax","Melting Wax",
    "Ink","Printer Ink","Spilled Ink","Reality Bending Ink",
    "Old Book","Library Book","Wet Book","Ancient Book",
    "Printer Toner","Exploded Toner","Toner Cloud","Toner Storm",
    "Cheese","Bread","Milk","Butter","Egg","Rice","Chicken","Beef","Pork","Fish",
    "Salt","Sugar","Honey","Jam","Coffee","Tea","Juice","Water","Soda","Soup",
    "Salad","Sandwich","Toast","Bagel","Muffin","Cake","Pie","Cookie","Brownie","Waffle",
    "Yogurt","Cereal","Oatmeal","Granola","Pasta","Noodles","Dumpling","Meatball","Sausage","Bacon",
    "Shrimp","Crab","Lobster","Tofu","Beans","Lentils","Chickpea","Corn","Potato","Tomato",
    "Onion","Garlic","Pepper","Carrot","Broccoli","Cabbage","Spinach","Mushroom","Cucumber","Zucchini",
    "Apple","Banana","Orange","Lemon","Lime","Grape","Blueberry","Raspberry","Mango","Pineapple",
    "Peach","Pear","Plum","Cherry","Watermelon","Melon","Avocado","Coconut","Almond","Peanut",
    "Walnut","Hazelnut","Cashew","Pistachio","Ice","Steam","Oil","Vinegar","Sauce",
    "Mustard","Ketchup","Mayonnaise","Relish","Pickle","Chili","Salsa","Guacamole","Hummus","Pesto",
    "Parmesan","Mozzarella","Cheddar","Gouda","Brie","Feta","Ricotta","Cream","Custard","Pudding",
    "Maple Syrup","Molasses","Toffee","Butterscotch","Marshmallow","Gelatin","Carrot Cake","Cupcake","Frosting","Icing",
    "Espresso","Latte","Cappuccino","Mocha","Matcha","Milkshake","Smoothie","Protein Shake","Broth","Gravy",
    "Quinoa","Barley","Wheat","Rye","Sourdough","Tortilla","Wrap","Burrito","Quesadilla","Nachos",
    "Clam","Oyster","Scallop","Anchovy","Sardine","Tuna","Salmon","Cod","Trout","Seaweed",
    "Wasabi","Horseradish","Ginger","Turmeric","Cinnamon","Nutmeg","Clove","Cardamom","Paprika","Cumin",
    "Vanilla Bean","Cocoa","Chocolate Chip","Caramel Sauce","Fruit","Berry","Citrus","Melon","Stonefruit","Nut",
    "Paella","Gazpacho","Tortilla Española","Ratatouille","Coq au Vin","Bouillabaisse","Cassoulet","Wiener Schnitzel","Bratwurst","Sauerbraten",
    "Goulash","Pierogi","Borscht","Beef Stroganoff","Pelmeni","Chicken Kiev","Haggis","Fish and Chips","Shepherd's Pie","Full English Breakfast",
    "Irish Stew","Smørrebrød","Gravlax","Meatballs","Lutefisk","Reindeer Stew","Fondue","Raclette","Rösti","Moussaka",
    "Souvlaki","Tzatziki","Dolma","Kebab","Shawarma","Falafel","Hummus Plate","Tabbouleh","Fattoush","Kabsa",
    "Mandi","Biryani","Butter Chicken","Tandoori Chicken","Dal","Chole Bhature","Masala Dosa","Idli","Sambar","Paneer Tikka",
    "Nasi Goreng","Satay","Rendang","Laksa","Pho","Banh Mi","Pad Thai","Tom Yum","Green Curry","Massaman Curry",
    "Sushi Roll","Tempura","Okonomiyaki","Takoyaki","Bibimbap","Bulgogi","Kimchi Stew","Hot Pot","Peking Duck","Xiaolongbao",
    "Mapo Tofu","Chow Mein","Fried Rice","Dim Sum","Char Siu","Adobo","Lechon","Halo Halo","Sisig","Jollof Rice",
    "Fufu","Egusi Soup","Bobotie","Bunny Chow","Piri Piri Chicken","Couscous","Tagine","Harira","Shakshuka","Ful Medames",
    "Koshari","Injera","Doro Wat","Sambusa","Pilaf","Plov","Lagman","Manty","Arepas","Empanadas",
    "Asado","Churrasco","Feijoada","Moqueca","Ceviche","Lomo Saltado","Aji de Gallina","Pupusas","Tamales","Tacos al Pastor",
    "Enchiladas","Guacamole","Pozole","Chiles Rellenos","Clam Chowder","Burger Classic","Buffalo Wings","Mac and Cheese","Cornbread","Jambalaya",
    "Gumbo","Poutine","Tourtiere","Butter Tart","Meat Pie","Lamington","Meat Pie Australian","Vegemite Toast","Pavlova","Hangi"
]

ALL_FLAVOURS_SET = set(ALL_FLAVOURS)
TOTAL_DISCOVERABLE_FLAVOURS = len(ALL_FLAVOURS_SET)

MAX_PARTICIPANTS = 5
EVENT_DURATION_SECONDS = 10 * 60  # 10 minutes

MIN_SPAWN_SECONDS = 5 * 60 * 60
MAX_SPAWN_SECONDS = 7 * 60 * 60

SOCK_EMOJI_POOL = [
    "<:Sock1:1485675915584344124>",
    "<:Sock2:1485675913499771061>",
    "<:Sock3:1485675911935168522>",
    "<:Sock4:1485675910467424408>",
    "<:Sock5:1485675909582295171>",
    "<:Sock6:1485677804581421128>",
    "<:Sock7:1485675907434811625>",
    "<:Sock8:1485675897389449287>",
    "<:Sock9:1485675896458444800>",
    "<:Sock10:1485676309253459988>",
]

SOCKS_PER_EVENT = 5

REWARD_BY_RANK = {
    1: 10,
    2: 5,
    3: 3,
    4: 2,
    5: 1,
}

DOBBY_RESPONSE_BY_RANK = {
    1: "Dobby is amazed! Such a magnificent sock! Master earns **10 Bertie Bott’s Every Flavoured Beans**!",
    2: "Oho! Dobby likes this one quite a lot. Master earns **5 Bertie Bott’s Every Flavoured Beans**!",
    3: "This sock is respectable. Dobby nods politely. Master earns **3 Bertie Bott’s Every Flavoured Beans**.",
    4: "Hmm. Dobby has seen better socks, but this one will do. Master earns **2 Bertie Bott’s Every Flavoured Beans**.",
    5: "This sock is... a choice. Dobby supposes Master may have **1 Bertie Bott’s Every Flavoured Bean**.",
}

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("dobby_bot")

# =========================================================
# DISCORD SETUP
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# JSON HELPERS
# =========================================================
def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        log.warning("Could not read %s, using default.", path.name)
        return default


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_files() -> None:
    if not INVENTORY_FILE.exists():
        save_json(INVENTORY_FILE, {})

    if not SETTINGS_FILE.exists():
        save_json(SETTINGS_FILE, {"allowed_channels": []})

    if not TASTED_FLAVOURS_FILE.exists():
        save_json(TASTED_FLAVOURS_FILE, {})

    if not FLAVORS_FILE.exists():
        save_json(FLAVORS_FILE, ALL_FLAVOURS)


ensure_files()

inventory_data: dict[str, dict[str, int]] = load_json(INVENTORY_FILE, {})
settings_data: dict[str, list[int]] = load_json(SETTINGS_FILE, {"allowed_channels": []})
tasted_flavours_data: dict[str, list[str]] = load_json(TASTED_FLAVOURS_FILE, {})

# =========================================================
# DATA HELPERS
# =========================================================
def get_user_inventory(user_id: int) -> dict[str, int]:
    uid = str(user_id)
    if uid not in inventory_data:
        inventory_data[uid] = {"beans": 0}
    return inventory_data[uid]

def reset_allowed_channels() -> None:
    settings_data["allowed_channels"] = []
    save_json(SETTINGS_FILE, settings_data)

def get_bean_count(user_id: int) -> int:
    return get_user_inventory(user_id)["beans"]


def add_beans(user_id: int, amount: int) -> int:
    if amount < 0:
        raise ValueError("amount must be >= 0")
    inv = get_user_inventory(user_id)
    inv["beans"] += amount
    save_json(INVENTORY_FILE, inventory_data)
    return inv["beans"]


def remove_bean(user_id: int) -> bool:
    inv = get_user_inventory(user_id)
    if inv["beans"] <= 0:
        return False
    inv["beans"] -= 1
    save_json(INVENTORY_FILE, inventory_data)
    return True


def get_flavors() -> list[str]:
    flavors = load_json(FLAVORS_FILE, ALL_FLAVOURS)
    if not isinstance(flavors, list):
        return ALL_FLAVOURS
    return [str(x) for x in flavors]


def get_user_tasted_flavours(user_id: int) -> set[str]:
    uid = str(user_id)
    raw = tasted_flavours_data.get(uid, [])
    return {str(x) for x in raw}


def add_tasted_flavour(user_id: int, flavour: str) -> tuple[bool, int]:
    uid = str(user_id)
    tasted = get_user_tasted_flavours(user_id)
    is_new = flavour not in tasted

    if is_new:
        tasted.add(flavour)
        tasted_flavours_data[uid] = sorted(tasted)
        save_json(TASTED_FLAVOURS_FILE, tasted_flavours_data)

    return is_new, len(tasted)


def get_allowed_channels() -> set[int]:
    raw = settings_data.get("allowed_channels", [])
    return {int(x) for x in raw}


def save_allowed_channels(channels: set[int]) -> None:
    settings_data["allowed_channels"] = sorted(channels)
    save_json(SETTINGS_FILE, settings_data)


def allow_channel(channel_id: int) -> None:
    channels = get_allowed_channels()
    channels.add(channel_id)
    save_allowed_channels(channels)


def disallow_channel(channel_id: int) -> None:
    channels = get_allowed_channels()
    channels.discard(channel_id)
    save_allowed_channels(channels)

# =========================================================
# EVENT STATE
# =========================================================
active_events: dict[int, "DobbyEvent"] = {}
spawn_loop_task: asyncio.Task | None = None

# =========================================================
# EVENT CLASS
# =========================================================
class DobbyEvent:
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self.channel_id = channel.id
        self.guild_id = channel.guild.id

        self.active = True
        self.gif_url = random.choice(EVENT_GIF_URLS)

        self.socks = random.sample(SOCK_EMOJI_POOL, SOCKS_PER_EVENT)
        self.assignment = self._create_assignment()

        self.participants: dict[int, dict[str, str]] = {}

        self.message: discord.Message | None = None
        self.view: "DobbyView | None" = None
        self.end_task: asyncio.Task | None = None

    def _create_assignment(self) -> dict[str, int]:
        ranks = [1, 2, 3, 4, 5]
        random.shuffle(ranks)
        return dict(zip(self.socks, ranks))

    def participant_count(self) -> int:
        return len(self.participants)

    def has_participated(self, user_id: int) -> bool:
        return user_id in self.participants

    def add_participant(self, member: discord.Member | discord.User, sock_emoji: str) -> tuple[int, int]:
        rank = self.assignment[sock_emoji]
        reward = REWARD_BY_RANK[rank]

        display_name = getattr(member, "display_name", member.name)
        self.participants[member.id] = {
            "name": display_name,
            "sock": sock_emoji,
        }

        add_beans(member.id, reward)
        return rank, reward

    def build_embed(self, ended_reason: str | None = None) -> discord.Embed:
        if self.participants:
            names = "\n".join(f"• {info['name']}" for info in self.participants.values())
        else:
            names = "Nobody yet."

        embed = discord.Embed(
            title=EVENT_TITLE,
            description=(
                f"{EVENT_DESCRIPTION}\n\n"
                f"**Participants:** {self.participant_count()}/{MAX_PARTICIPANTS}\n"
                f"**People who already interacted:**\n{names}"
            ),
            color=discord.Color.green(),
        )
        embed.set_image(url=self.gif_url)
        embed.set_footer(text="Event ends after 10 minutes or when 5 unique users have interacted.")

        if ended_reason:
            embed.add_field(name="Event ended", value=ended_reason, inline=False)

        return embed

    async def send(self) -> None:
        self.view = DobbyView(self)
        self.message = await self.channel.send(embed=self.build_embed(), view=self.view)
        self.end_task = asyncio.create_task(self._auto_end())

    async def refresh_message(self) -> None:
        if self.message and self.view:
            await self.message.edit(embed=self.build_embed(), view=self.view)

    async def _auto_end(self) -> None:
        await asyncio.sleep(EVENT_DURATION_SECONDS)
        if self.active:
            await self.end("Dobby got bored and vanished after 10 minutes.", delete_message=True)

    async def end(self, reason: str, delete_message: bool = False) -> None:
        if not self.active:
            return

        self.active = False

        if self.view:
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

        if self.end_task and not self.end_task.done():
            self.end_task.cancel()

        active_events.pop(self.channel_id, None)

        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                log.exception("Failed to delete Dobby event message in #%s", self.channel.name)

        try:
            await self.channel.send(
                "Dobby disappeared — and you just missed him! "
                "But surely he’ll be back again soon with more socks to inspect..."
            )
        except discord.HTTPException:
            log.exception("Failed to send Dobby disappearance message in #%s", self.channel.name)

# =========================================================
# BUTTON VIEW
# =========================================================
class SockButton(discord.ui.Button["DobbyView"]):
    def __init__(self, sock_emoji: str, index: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=sock_emoji,
            custom_id=f"dobby_button_sock_{index}",
        )
        self.sock_emoji = sock_emoji

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            await interaction.response.send_message(
                "This button is not available right now.",
                ephemeral=True,
            )
            return

        await self.view.handle_press(interaction, self.sock_emoji)


class DobbyView(discord.ui.View):
    def __init__(self, event: DobbyEvent):
        super().__init__(timeout=None)
        self.event = event

        for index, sock_emoji in enumerate(event.socks, start=1):
            self.add_item(SockButton(sock_emoji, index))

    async def handle_press(self, interaction: discord.Interaction, sock_emoji: str) -> None:
        if not self.event.active:
            await interaction.response.send_message(
                "Too late — Dobby has already left.",
                ephemeral=True,
            )
            return

        if self.event.has_participated(interaction.user.id):
            await interaction.response.send_message(
                "You already interacted with this Dobby event.",
                ephemeral=True,
            )
            return

        rank, reward = self.event.add_participant(interaction.user, sock_emoji)
        total = get_bean_count(interaction.user.id)
        bean_word = "Bean" if reward == 1 else "Beans"

        await self.event.refresh_message()

        await interaction.response.send_message(
            f"{DOBBY_RESPONSE_BY_RANK[rank]}\n\n"
            f"You received **{reward} Bertie Bott’s Every Flavoured {bean_word}**.\n"
            f"You now have **{total} Bertie Bott’s Every Flavoured Beans**.",
            ephemeral=True,
        )

        if self.event.participant_count() >= MAX_PARTICIPANTS:
            await self.event.end("5 unique people interacted with Dobby.")

# =========================================================
# EVENT HELPERS
# =========================================================
async def start_dobby_event(channel: discord.TextChannel) -> tuple[bool, str]:
    if channel.id in active_events:
        return False, "A Dobby event is already active in this channel."

    event = DobbyEvent(channel)
    active_events[channel.id] = event
    await event.send()
    return True, "Dobby has appeared."


def get_valid_allowed_channels() -> list[discord.TextChannel]:
    channels: list[discord.TextChannel] = []

    for channel_id in get_allowed_channels():
        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            continue
        if channel.id in active_events:
            continue
        channels.append(channel)

    return channels


def choose_spawn_channel() -> discord.TextChannel | None:
    channels = get_valid_allowed_channels()
    if not channels:
        return None
    return random.choice(channels)

# =========================================================
# RANDOM SPAWN LOOP
# =========================================================
async def random_spawn_loop() -> None:
    await bot.wait_until_ready()

    while not bot.is_closed():
        delay = random.randint(MIN_SPAWN_SECONDS, MAX_SPAWN_SECONDS)
        log.info("Next Dobby spawn check in %s seconds.", delay)
        await asyncio.sleep(delay)

        channel = choose_spawn_channel()
        if channel is None:
            log.info("No allowed channel available for Dobby spawn.")
            continue

        try:
            _, message = await start_dobby_event(channel)
            log.info("Spawn attempt in #%s: %s", channel.name, message)
        except Exception:
            log.exception("Failed to start Dobby event.")

# =========================================================
# PERMISSION HELPERS
# =========================================================
def admin_only() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.CheckFailure("This command can only be used in a server.")
        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure("You must be an administrator to use this command.")
        return True

    return app_commands.check(predicate)



# =========================================================
# PUBLIC COMMANDS
# =========================================================
@bot.tree.command(name="eat_bean", description="Eat one Bertie Bott's Every Flavoured Bean.")
async def eat_bean(interaction: discord.Interaction) -> None:
    if not remove_bean(interaction.user.id):
        await interaction.response.send_message(
            "You do not have any Bertie Bott’s Every Flavoured Beans to eat.",
            ephemeral=True,
        )
        return

    flavors = get_flavors()
    flavor = random.choice(flavors) if flavors else "Mystery flavour"
    remaining = get_bean_count(interaction.user.id)

    is_new_flavour, discovered_count = add_tasted_flavour(interaction.user.id, flavor)
    bean_image_url = random.choice(BEAN_IMAGE_URLS)

    familiarity_text = (
        "Unfamiliar flavour — a new discovery."
        if is_new_flavour
        else f"Familiar flavour — {interaction.user.display_name} has tasted this before."
    )

    embed = discord.Embed(
        description=(
            f"{interaction.user.display_name} just ate a Bertie Bott’s Every Flavoured Bean...\n"
            f"it tastes like...\n\n"
            f"**__🍬  {flavor.upper()}  🍬__**\n\n"
            f"*{familiarity_text}*\n"
            f"`{discovered_count}/{TOTAL_DISCOVERABLE_FLAVOURS} flavours discovered`"
        ),
        color=discord.Color.green(),
    )

    embed.set_thumbnail(url=bean_image_url)
    embed.set_footer(text=f"{remaining} beans left")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="inventory", description="See how many Bertie Bott's Every Flavoured Beans you currently have.")
async def inventory(interaction: discord.Interaction) -> None:
    count = get_bean_count(interaction.user.id)
    bean_word = "Bean" if count == 1 else "Beans"
    await interaction.response.send_message(
        f"You currently have **{count} Bertie Bott’s Every Flavoured {bean_word}**.",
        ephemeral=True,
    )

# =========================================================
# ADMIN COMMANDS
# =========================================================
@bot.tree.command(name="dobby_trigger", description="Force Dobby to appear in this channel.")
@admin_only()
async def dobby_trigger(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "This command must be used in a server text channel.",
            ephemeral=True,
        )
        return

    _, message = await start_dobby_event(interaction.channel)
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="dobby_allow_here", description="Allow Dobby to randomly appear in this channel.")
@admin_only()
async def dobby_allow_here(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "This command must be used in a server text channel.",
            ephemeral=True,
        )
        return

    allow_channel(interaction.channel.id)
    await interaction.response.send_message(
        f"Dobby is now allowed to appear in {interaction.channel.mention}.",
        ephemeral=True,
    )

@bot.tree.command(name="dobby_reset_channels", description="Remove all channels where Dobby is allowed to spawn.")
@admin_only()
async def dobby_reset_channels(interaction: discord.Interaction) -> None:
    reset_allowed_channels()

    await interaction.response.send_message(
        "All allowed Dobby channels have been cleared. "
        "Dobby will no longer spawn anywhere until new channels are added.",
        ephemeral=True,
    )


@bot.tree.command(name="dobby_disallow_here", description="Stop Dobby from randomly appearing in this channel.")
@admin_only()
async def dobby_disallow_here(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "This command must be used in a server text channel.",
            ephemeral=True,
        )
        return

    disallow_channel(interaction.channel.id)
    await interaction.response.send_message(
        f"Dobby will no longer randomly appear in {interaction.channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="give_beans", description="Give a user Bertie Bott's Every Flavoured Beans.")
@admin_only()
@app_commands.describe(user="The user to receive beans", amount="How many Bertie Bott's Every Flavoured Beans to give")
async def give_beans(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 100000],
) -> None:
    new_total = add_beans(user.id, amount)
    bean_word = "Bean" if amount == 1 else "Beans"
    total_word = "Bean" if new_total == 1 else "Beans"
    await interaction.response.send_message(
        f"Gave **{amount} Bertie Bott’s Every Flavoured {bean_word}** to {user.mention}. "
        f"They now have **{new_total} Bertie Bott’s Every Flavoured {total_word}**."
    )


@bot.tree.command(name="dobby_channels", description="Show all channels where Dobby may randomly appear.")
@admin_only()
async def dobby_channels(interaction: discord.Interaction) -> None:
    channels = get_allowed_channels()
    if not channels:
        await interaction.response.send_message(
            "No channels are currently allowed for random Dobby spawns.",
            ephemeral=True,
        )
        return

    mentions = []
    for channel_id in sorted(channels):
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            mentions.append(channel.mention)
        else:
            mentions.append(f"`{channel_id}` (not found)")

    await interaction.response.send_message(
        "Allowed Dobby channels:\n" + "\n".join(f"• {m}" for m in mentions),
        ephemeral=True,
    )

# =========================================================
# ERROR HANDLER
# =========================================================
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(str(error), ephemeral=True)
        return

    log.exception("Unhandled app command error", exc_info=error)

    if interaction.response.is_done():
        await interaction.followup.send(
            "Something went wrong while running that command.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Something went wrong while running that command.",
            ephemeral=True,
        )

# =========================================================
# READY
# =========================================================
@bot.event
async def on_ready() -> None:
    global spawn_loop_task

    synced = await bot.tree.sync()
    log.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")
    log.info("Synced %s slash commands.", len(synced))

    if spawn_loop_task is None or spawn_loop_task.done():
        spawn_loop_task = asyncio.create_task(random_spawn_loop())
        log.info("Random Dobby spawn loop started.")

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            'DISCORD_TOKEN is not set. Run:\nexport DISCORD_TOKEN="your_token_here"'
        )

    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()