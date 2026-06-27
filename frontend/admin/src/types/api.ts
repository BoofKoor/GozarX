// Response/request shapes for the GozarX admin API (`/api/admin/*`, Phase 7a).

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Me {
  username: string;
}

export interface SetupStatus {
  completed: boolean;
}

export interface Squad {
  uuid: string;
  name: string;
}

export interface EconomicsSettings {
  trial_squad: string | null;
  locations: string[];
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  ads_enabled: boolean;
}

export type SettingsPatch = Partial<Omit<EconomicsSettings, "trial_squad">>;

export interface SetupPayload {
  trial_squad: string;
  locations: string[];
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  ads_enabled: boolean;
}

export interface DayPoint {
  day: string;
  count: number;
}

export interface DashboardStats {
  total_users: number;
  available: number;
  active: number;
  banned: number;
  configs_today: number;
  referrals: number;
  claims_series: DayPoint[];
}

// --- Phase 7c: texts + buttons editors ---
export type Lang = "fa" | "en" | "ru";
export type LabelMap = Record<Lang, string>;

export interface BotText {
  key: string;
  fa: string;
  en: string;
  ru: string;
  placeholders: string[];
}

export type TextPatch = Partial<Record<Lang, string>>;

export interface TextPreview {
  rendered: string;
  missing_placeholders: string[];
}

export interface ButtonConfig {
  key: string;
  screen: string;
  is_critical: boolean;
  is_visible: boolean;
  default_row: number;
  default_position: number;
  effective_row: number;
  effective_position: number;
  default_label: LabelMap;
  effective_label: LabelMap;
  customized: boolean;
}

export interface ButtonAppearancePatch {
  labels: Partial<LabelMap> | null;
  is_visible: boolean;
}

export interface ReorderItem {
  key: string;
  row_index: number;
  position: number;
}
