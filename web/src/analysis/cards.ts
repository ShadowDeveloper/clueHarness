// Edition card data — mirror of clue/rules/cards.py (kept in sync by the fixture cross-validation tests).

export type Edition = "classic" | "modern" | "large";

const SUSPECTS_CLASSIC = ["Miss Scarlet", "Col. Mustard", "Mrs. White", "Mr. Green", "Mrs. Peacock", "Prof. Plum"];
const SUSPECTS_MODERN = SUSPECTS_CLASSIC.map((s) => (s === "Mrs. White" ? "Dr. Orchid" : s));
const WEAPONS = ["Candlestick", "Dagger", "Lead Pipe", "Revolver", "Rope", "Wrench"];
const ROOMS = ["Hall", "Lounge", "Dining Room", "Kitchen", "Ballroom", "Conservatory", "Billiard Room", "Library", "Study"];
const SUSPECTS_LARGE = [...SUSPECTS_CLASSIC, "Wadsworth", "Yvette", "Miss Peach", "Sgt. Gray", "Mr. Boddy", "Madame Rose"];
const WEAPONS_LARGE = [...WEAPONS, "Poison", "Horseshoe", "Axe", "Trophy", "Poker", "Garden Shears"];
const ROOMS_LARGE = ["Hall", "Lounge", "Dining Room", "Kitchen", "Ballroom", "Conservatory", "Attic", "Cellar", "Garage", "Gazebo", "Courtyard", "Carriage House"];

export interface EditionDef {
  id: Edition;
  label: string;
  suspects: string[];
  weapons: string[];
  rooms: string[];
  maxPlayers: number;
}

export const EDITIONS: Record<Edition, EditionDef> = {
  classic: { id: "classic", label: "Classic (6-6-9, 3-6 players)", suspects: SUSPECTS_CLASSIC, weapons: WEAPONS, rooms: ROOMS, maxPlayers: 6 },
  modern: { id: "modern", label: "Modern 2016 (Dr. Orchid)", suspects: SUSPECTS_MODERN, weapons: WEAPONS, rooms: ROOMS, maxPlayers: 6 },
  large: { id: "large", label: "Large - Hill House (12-12-12, 3-12 players)", suspects: SUSPECTS_LARGE, weapons: WEAPONS_LARGE, rooms: ROOMS_LARGE, maxPlayers: 12 },
};

export const EDITION_IDS = Object.keys(EDITIONS) as Edition[];

export function editionDef(edition: string): EditionDef {
  const def = EDITIONS[edition as Edition];
  if (!def) throw new Error(`unknown edition ${edition}`);
  return def;
}

export function allCards(edition: string): string[] {
  const d = editionDef(edition);
  return [...d.suspects, ...d.weapons, ...d.rooms];
}

export function nDealt(edition: string): number {
  return allCards(edition).length - 3;
}

export function categoryOf(card: string, edition: string): "suspect" | "weapon" | "room" | null {
  const d = editionDef(edition);
  if (d.suspects.includes(card)) return "suspect";
  if (d.weapons.includes(card)) return "weapon";
  if (d.rooms.includes(card)) return "room";
  return null;
}
