/**
 * Mirrors apps/api/app/domain/phone.py exactly — the same pairing
 * whatsapp.ts has with app/domain/whatsapp.py, and for the same reason: the
 * two sides have to agree on what "the same number" means.
 *
 * The server is still the authority; it normalizes everything it stores
 * (decision 44). This copy exists so a form can tell someone their number
 * cannot be right *while they are still looking at the field*, instead of a
 * round trip that lands on "something went wrong" three steps later.
 *
 * Lebanese numbers need no country code; any other number is accepted when
 * written with + or 00 and its country code (decision 49).
 */
export function normalizePhone(value: string): string | null {
  const written = value.trim()
  let digits = written.replace(/[^\d]/g, '')
  if (!digits) return null

  const international = written.startsWith('+') || digits.startsWith('00')
  if (digits.startsWith('00')) digits = digits.slice(2)

  if (digits.startsWith('961') && (international || digits.length === 10 || digits.length === 11)) {
    const national = digits.slice(3)
    // +961 with the wrong length is a mistyped Lebanese number.
    return national.length === 7 || national.length === 8 ? `+961${national}` : null
  }

  // E.164: at most 15 digits with the country code.
  if (international) return digits.length >= 8 && digits.length <= 15 ? `+${digits}` : null

  // A local trunk prefix: 03 123456 is the same number as +961 3 123456.
  const national = digits.startsWith('0') ? digits.slice(1) : digits
  // Lebanese mobiles are 7 digits (03 X XX XX XX) or 8 (70/71/76/78/79/81).
  return national.length === 7 || national.length === 8 ? `+961${national}` : null
}
