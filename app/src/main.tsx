import { createRoot } from "react-dom/client";
import "maplibre-gl/dist/maplibre-gl.css";
import { App } from "@/components/App";
import "@/styles/globals.css";

createRoot(document.getElementById("app")!).render(<App />);
