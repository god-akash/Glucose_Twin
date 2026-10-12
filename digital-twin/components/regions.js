// One entry per body system. accent = UI colour, glow/deep = background light and shadow.
export const DEFAULT = {
  id: null,
  accent: "#9fe8dc",
  title: "A living model of your health.",
  text: "Hover over the body to see what your twin tracks. Your doctor sees the same model, updated daily.",
};

export const REGIONS = {
  heart: {
    id: "heart", name: "Heart", accent: "#ff6b81", glow: "#ff2d55", deep: "#1c050b",
    title: "Your heart, checked every day.",
    text: "Resting rate, rhythm and blood pressure trends. Changes show up weeks before you would feel them.",
    reading: "Sample: resting 62 bpm, steady rhythm",
  },
  lungs: {
    id: "lungs", name: "Lungs", accent: "#7cc4ff", glow: "#2d8cff", deep: "#04142b",
    title: "Breathing, measured while you sleep.",
    text: "Overnight oxygen and breathing rate, compared with your own baseline instead of a textbook average.",
    reading: "Sample: SpO₂ 98%, 14 breaths per minute",
  },
  brain: {
    id: "brain", name: "Brain", accent: "#b79cff", glow: "#7a5cff", deep: "#120930",
    title: "Sleep and focus, in one view.",
    text: "Sleep stages, stress load and recovery. Your doctor sees patterns, not single bad nights.",
    reading: "Sample: 7h 20m asleep, recovery 81%",
  },
  gut: {
    id: "gut", name: "Gut", accent: "#f2b84b", glow: "#ffa41f", deep: "#1f1303",
    title: "Digestion, without the guesswork.",
    text: "Log meals and symptoms, then see which foods line up with flare-ups.",
    reading: "Sample: 2 likely triggers found in 30 days",
  },
  joints: {
    id: "joints", name: "Joints", accent: "#6be3a0", glow: "#22d98a", deep: "#031b12",
    title: "Movement that stays pain-free.",
    text: "Gait and joint-load scans flag uneven loading in knees and elbows before it turns into pain.",
    reading: "Sample: left knee carries 12% more load",
  },
};