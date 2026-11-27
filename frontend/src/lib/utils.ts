import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
/** Merge shadcn utility classes. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
