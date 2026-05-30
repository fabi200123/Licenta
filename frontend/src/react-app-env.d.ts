/// <reference types="react-scripts" />

declare namespace NodeJS {
  interface ProcessEnv {
    REACT_APP_DASH_APP_URL?: string;
    REACT_APP_DASH_APP_INTERNAL_URL?: string;
  }
}
