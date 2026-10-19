// The body regions are educational context for glucose health, not live measurements.
export const DEFAULT = {
  id: null,
  accent: "#9fe8dc",
  title: "A clearer view of glucose risk.",
  text: "Glucose Twin brings glucose readings and model-based high- and low-glucose risk estimates into one dashboard. Explore the anatomy, then open the dashboard to see data from the FastAPI service.",
};

export const REGIONS = {
  heart: {
    id: "heart", name: "Heart", accent: "#ff6b81", glow: "#ff2d55", deep: "#1c050b",
    title: "Glucose health and the heart.",
    text: "Over time, glucose levels can be one part of a person’s wider cardiovascular health. This highlighted anatomy is illustrative; the dashboard does not monitor heart function.",
  },
  lungs: {
    id: "lungs", name: "Lungs", accent: "#7cc4ff", glow: "#2d8cff", deep: "#04142b",
    title: "A glucose twin, not a whole-body monitor.",
    text: "The 3D anatomy provides context for the glucose dashboard. The current backend does not measure breathing, oxygen, or lung function.",
  },
  brain: {
    id: "brain", name: "Brain", accent: "#b79cff", glow: "#7a5cff", deep: "#120930",
    title: "Glucose readings become model inputs.",
    text: "The backend uses recent glucose history to estimate the chance of crossing configured high- or low-glucose thresholds within future time windows.",
  },
  gut: {
    id: "gut", name: "Gut", accent: "#f2b84b", glow: "#ffa41f", deep: "#1f1303",
    title: "Meals add useful context.",
    text: "When meal data is provided, its timing and logged nutrients can be used by the model. The system does not identify food triggers or give meal advice.",
  },
  joints: {
    id: "joints", name: "Joints", accent: "#6be3a0", glow: "#22d98a", deep: "#031b12",
    title: "Wearable data can add activity context.",
    text: "The API accepts activity and heart-rate observations as model inputs. This project does not assess joints, gait, or pain.",
  },
};