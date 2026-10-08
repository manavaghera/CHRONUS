import { APP } from './app'
import { HOME } from './home'
import { CREATE } from './create'
import { TOOLS } from './tools'

// Each strings file is a list of [English, हिन्दी, ગુજરાતી] triples. This
// module is loaded only when someone picks Hindi or Gujarati (see i18n.jsx).
export const TRIPLES = [...APP, ...HOME, ...CREATE, ...TOOLS]
export const DICTS = {
  hi: Object.fromEntries(TRIPLES.map(([en, hi]) => [en, hi])),
  gu: Object.fromEntries(TRIPLES.map(([en, , gu]) => [en, gu])),
}
