export function getDashAppBaseUrl(): string {
  const configured = process.env.REACT_APP_DASH_APP_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const nodePort = process.env.REACT_APP_DASH_APP_NODE_PORT ?? "30001";
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:${nodePort}`;
}

export function getVisualizationUrl(cnp: string): string {
  return `${getDashAppBaseUrl()}/visualize?cnp=${encodeURIComponent(cnp)}`;
}
