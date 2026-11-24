import { Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { readTheme, saveTheme, type ThemeChoice } from "@/lib/theme";

const order: ThemeChoice[] = ["system", "light", "dark"];
const meta = {
  system: { icon: Monitor, label: "Theme: match system" },
  light: { icon: Sun, label: "Theme: light" },
  dark: { icon: Moon, label: "Theme: dark" },
} as const;

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  const { icon: Icon, label } = meta[choice];
  const next = () => {
    const value = order[(order.indexOf(choice) + 1) % order.length] ?? "system";
    saveTheme(value);
    setChoice(value);
  };
  return (
    <Button variant="ghost" size="icon" onClick={next} aria-label={label} title={label}>
      <Icon />
    </Button>
  );
}
