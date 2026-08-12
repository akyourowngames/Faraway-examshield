import "@testing-library/jest-dom";

// jsdom does not implement matchMedia, but framer-motion reads it (e.g. for
// reduced-motion). Provide a no-op so component renders don't throw in tests.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}
