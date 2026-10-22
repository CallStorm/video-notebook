/** Skin / appearance tokens for Video Notebook. */
export type SkinId = "cloud" | "ink" | "sand" | "bamboo";

export const SKIN_STORAGE_KEY = "vn-skin";
export const DARK_STORAGE_KEY = "vn-dark";

export const SKINS: {
  id: SkinId;
  label: string;
  hint: string;
  /** Preview swatches: primary, violet/accent, background tint */
  swatches: [string, string, string];
}[] = [
  {
    id: "cloud",
    label: "云青",
    hint: "冷白 · 电光蓝",
    swatches: ["#3B6FF5", "#7C5CF0", "#F4F6FA"],
  },
  {
    id: "ink",
    label: "墨夜",
    hint: "深底 · 靛紫辉光",
    swatches: ["#8B7CFF", "#A78BFA", "#141822"],
  },
  {
    id: "sand",
    label: "暖沙",
    hint: "米色纸感 · 赤陶",
    swatches: ["#C45C26", "#D4A017", "#F7F1E8"],
  },
  {
    id: "bamboo",
    label: "竹青",
    hint: "薄荷灰 · 玉绿",
    swatches: ["#2A9B7A", "#5CB88A", "#F0F5F2"],
  },
];

const SKIN_IDS = new Set<string>(SKINS.map((s) => s.id));

export function isSkinId(value: string | null | undefined): value is SkinId {
  return !!value && SKIN_IDS.has(value);
}

export function readStoredSkin(): SkinId {
  try {
    const raw = localStorage.getItem(SKIN_STORAGE_KEY);
    if (isSkinId(raw)) return raw;
  } catch {
    /* private mode */
  }
  return "bamboo";
}

export function readStoredDark(): boolean {
  try {
    const raw = localStorage.getItem(DARK_STORAGE_KEY);
    if (raw === "1" || raw === "true") return true;
    if (raw === "0" || raw === "false") return false;
  } catch {
    /* private mode */
  }
  // 墨夜默认偏深：未显式设置过深色时，选墨夜则开深色
  return readStoredSkin() === "ink";
}

/** Apply skin (+ optional dark) to <html>. Call before first paint when possible. */
export function applyAppearance(skin: SkinId, dark?: boolean) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.skin = skin;
  const useDark = dark ?? readStoredDark();
  root.classList.toggle("dark", useDark);
}

export function persistSkin(skin: SkinId) {
  try {
    localStorage.setItem(SKIN_STORAGE_KEY, skin);
  } catch {
    /* ignore */
  }
  // 切换到墨夜且从未显式设过深色偏好时，自动偏深
  let dark = false;
  try {
    const raw = localStorage.getItem(DARK_STORAGE_KEY);
    if (raw === "1" || raw === "true") dark = true;
    else if (raw === "0" || raw === "false") dark = false;
    else dark = skin === "ink";
  } catch {
    dark = skin === "ink";
  }
  applyAppearance(skin, dark);
}

export function persistDark(dark: boolean) {
  try {
    localStorage.setItem(DARK_STORAGE_KEY, dark ? "1" : "0");
  } catch {
    /* ignore */
  }
  applyAppearance(readStoredSkin(), dark);
}

/** Boot: read storage and stamp <html> before React mounts. */
export function bootAppearance() {
  const skin = readStoredSkin();
  let dark: boolean;
  try {
    const raw = localStorage.getItem(DARK_STORAGE_KEY);
    if (raw === "1" || raw === "true") dark = true;
    else if (raw === "0" || raw === "false") dark = false;
    else dark = skin === "ink";
  } catch {
    dark = skin === "ink";
  }
  applyAppearance(skin, dark);
}
