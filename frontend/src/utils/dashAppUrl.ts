export function getVisualizationUrl(cnp: string): string {
  const configured = process.env.REACT_APP_DASH_APP_URL?.trim();
  const query = `cnp=${encodeURIComponent(cnp)}`;

  if (configured) {
    const base = configured.replace(/\/$/, "");
    return `${base}/visualize?${query}`;
  }

  return `/visualize?${query}`;
}
