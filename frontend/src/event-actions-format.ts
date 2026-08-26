export function buildRouteUrl(latitude: number, longitude: number): string {
  return "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(latitude + "," + longitude);
}

export function isResolvedStatus(status: string | null | undefined): boolean {
  return status === "resolvido";
}
