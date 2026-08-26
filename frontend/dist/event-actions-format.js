export function buildRouteUrl(latitude, longitude) {
    return "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(latitude + "," + longitude);
}
export function isResolvedStatus(status) {
    return status === "resolvido";
}
