from dataclasses import dataclass


@dataclass(slots=True)
class MemberRoleContext:
    user_id: int
    role_ids: list[int]
    role_names: list[str]
    house_roles: list[str]
    current_house: str | None
    has_arena_role: bool