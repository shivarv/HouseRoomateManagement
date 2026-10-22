import type { ShoppingCategory } from "../../types/api";

/** Display order and labels. Mirrored in iOS (ShoppingView.swift). */
export const CATEGORIES: { key: ShoppingCategory; label: string; icon: string }[] = [
  { key: "groceries", label: "Groceries", icon: "🥚" },
  { key: "toiletries", label: "Toiletries", icon: "🧴" },
  { key: "cleaning", label: "Cleaning", icon: "🧼" },
  { key: "household", label: "Household", icon: "🧻" },
  { key: "other", label: "Other", icon: "🛍️" },
];

/** Quick-add chips. The backend works out the category from the name. */
export const SHOPPING_PRESETS = [
  "Eggs", "Milk", "Rice", "Oil", "Bread", "Onions",
  "Shampoo", "Toothpaste", "Hand wash",
  "Washing soap", "Dish soap", "Garbage bags",
  "Tissues", "Toilet paper", "Paper towels",
];
