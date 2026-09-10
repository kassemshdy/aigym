/**
 * Lebanon runs on WhatsApp: no Business API, no per-message cost, no Meta approval.
 * We compose the text and hand it to WhatsApp — a human taps send, which also keeps
 * the gym's number from being reported for automated blasts.
 */
export function waLink(phone: string, message: string) {
  const digits = phone.replace(/[^\d]/g, '')
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`
}
