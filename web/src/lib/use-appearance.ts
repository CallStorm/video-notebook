import { useCallback, useEffect, useState } from "react";
import {
  applyAppearance,
  bootAppearance,
  persistDark,
  persistSkin,
  readStoredDark,
  readStoredSkin,
  type SkinId,
} from "@/lib/skin";

export function useAppearance(): {
  skin: SkinId;
  dark: boolean;
  setSkin: (next: SkinId) => void;
  setDark: (next: boolean) => void;
} {
  const [skin, setSkinState] = useState<SkinId>(() =>
    typeof window === "undefined" ? "cloud" : readStoredSkin(),
  );
  const [dark, setDarkState] = useState<boolean>(() =>
    typeof window === "undefined" ? false : readStoredDark(),
  );

  useEffect(() => {
    bootAppearance();
  }, []);

  const setSkin = useCallback((next: SkinId) => {
    persistSkin(next);
    setSkinState(next);
    setDarkState(readStoredDark());
  }, []);

  const setDark = useCallback((next: boolean) => {
    persistDark(next);
    setDarkState(next);
    applyAppearance(readStoredSkin(), next);
  }, []);

  return { skin, dark, setSkin, setDark };
}
