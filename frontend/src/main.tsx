import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { GeographyBrowser } from "./components/GeographyBrowser";
import "./styles/app.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root not found in index.html");
}

createRoot(container).render(
  <StrictMode>
    <GeographyBrowser />
  </StrictMode>,
);
