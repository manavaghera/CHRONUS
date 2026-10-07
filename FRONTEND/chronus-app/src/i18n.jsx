import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { CHAT } from './strings/chat'
import { HOME } from './strings/home'
import { PAGES } from './strings/pages'

// The website in English, Hindi and Gujarati. Navigation, the Create flow
// (consent included) and the memory browser are here; the home page, the
// other pages and the chat are in strings/. Consent statements
// themselves come from the server (GET /consent-text), so the words shown are
// exactly the words the consent record keeps. The Hindi and Gujarati were
// drafted for CHRONUS; have a native speaker check them.

export const LANGUAGES = [['en', 'English'], ['hi', 'हिन्दी'], ['gu', 'ગુજરાતી']]
const KEY = 'chronus-language'

const CORE = {
  en: {
    'nav.home': 'Home', 'nav.demo': 'Live Demo', 'nav.models': 'Models', 'nav.create': 'Create', 'nav.roundtable': 'Roundtable',
    'nav.voice': 'Voice', 'nav.insights': 'Insights', 'nav.trust': 'Trust', 'nav.menu': 'Menu', 'nav.localTime': 'Local time',
    'nav.close': 'Close', 'nav.getStarted': 'Get Started', 'nav.createYourModel': 'Create Your Model', 'nav.voiceSandbox': 'Voice Sandbox',
    'nav.howItWorks': 'How It Works', 'nav.roadmap': 'Roadmap', 'nav.contact': 'Contact', 'nav.language': 'Language',

    'create.eyebrow': 'Create your model', 'create.building': 'Building {name}', 'create.preserve': 'Preserve someone’s memory',
    'create.sub': 'Their own words, collected with consent. CHRONUS answers only from what you add here, and shows the source of every answer.',
    'create.step.details': 'Details & consent', 'create.step.upload': 'Upload documents', 'create.step.interview': 'Interview', 'create.step.build': 'Build',
    'create.who': '1. Who is this model of?', 'create.name': 'Name', 'create.namePlaceholder': 'e.g. Amma, or Dr. Rao',
    'create.desc': 'Short description (optional)', 'create.descPlaceholder': 'e.g. Retired schoolteacher from Vadodara',
    'create.relationship': 'Your relationship to them',
    'rel.self': 'This is me', 'rel.family': 'Family member', 'rel.friend': 'Friend', 'rel.colleague': 'Colleague', 'rel.other': 'Other',
    'create.memorialTitle': 'They have passed away.',
    'create.memorialText': 'Memorial mode: answers are framed as remembered words, the model never speaks as if they were alive or present, and long sessions get a gentle reminder to take a break.',
    'create.aiTitle': 'Allow AI voice.',
    'create.aiText': 'Phrasing answers in their voice sends short excerpts of these memories to a cloud AI service (OpenRouter). Leave this off to keep everything on this computer; the model then answers with verbatim quotes.',
    'create.consentTitle': 'Consent.', 'create.staysHere': 'Everything stays in this CHRONUS install. You can delete it all later.',
    'create.createModel': 'Create model', 'create.creating': 'Creating…',
    'create.buildTitle': '4. Build', 'create.memoriesSoFar': '{count} memories so far ({needed} needed).',
    'create.ready': 'The model is ready. New documents and answers are added to it right away.',
    'create.notReady': 'Memories are embedded as you add them; building checks there is enough to answer from.',
    'create.buildModel': 'Build model', 'create.buildingNow': 'Building…', 'create.chatWith': 'Chat with {name}',
    'create.voiceTitle': '5. Voice', 'create.optional': 'optional',
    'create.voiceIntro': 'A clear 6-60 second recording (any audio format) of {name} speaking lets answers be read aloud in their voice. Fish Audio (a cloud service) turns it into a private voice; removing the voice, or the model, deletes it there and here.',
    'create.voiceConsentTitle': 'Voice consent.', 'create.cloudTitle': 'Cloud processing.',
    'create.cloudText': 'I agree that the recording, and the text of each answer I play, is sent to Fish Audio to make and use the voice.',
    'create.chooseRecording': 'Choose a recording', 'create.makingVoice': 'Making voice…', 'create.removeVoice': 'Remove voice',
    'create.voiceAdded': 'Voice added', 'create.reviewMemories': 'Review or correct its memories →', 'create.seeQuestions': 'See what people ask it →',

    'consent.title': 'Consent and privacy',
    'consent.intro': 'Consent can change. The person who gave it, or their family, can pause this model, renew consent each year, keep topics private, or revoke it, which deletes everything.',
    'consent.active': 'Active. Consent is reviewed by {date}.', 'consent.aYear': 'a year after it was given',
    'consent.due': 'Consent was due for review on {date}, so nobody can chat with {name} until it is renewed.',
    'consent.paused': 'Paused: nobody can chat with {name} until it is resumed.',
    'consent.pause': 'Pause', 'consent.resume': 'Resume', 'consent.renew': 'Renew consent for a year', 'consent.revoke': 'Revoke consent',
    'consent.revokeConfirm': 'Revoke consent for {name}? This deletes the model and everything in it: memories, documents, interview answers and voice. It cannot be undone.',
    'consent.topicsLabel': 'Topics that are off limits (comma-separated). Questions about them are refused, and memories that mention them are never quoted.',
    'consent.topicsPlaceholder': 'e.g. divorce, the hospital', 'consent.saveTopics': 'Save topics', 'consent.saved': '✓ Saved',
    'consent.neverQuoteHint': 'To keep one memory but never quote it, use “Never quote” when you review its memories.',

    'chat.ask': 'Ask {name} anything...', 'chat.aiVoice': 'AI voice', 'chat.quotesOnly': 'Quotes only', 'chat.sources': 'Sources',
    'chat.viewInContext': 'View in context', 'chat.watchAt': 'Watch at {at}', 'chat.viewPost': 'View the post', 'chat.openSource': 'Open the source',
    'chat.quoting': 'Quoting', 'chat.replyingTo': 'Replying to', 'chat.aPost': 'a post',
    'chat.speakerNote': "This transcript doesn't name its speakers, so the interviewer's words may be mixed in.",
    'chat.playOriginal': '▶ Play the original', 'chat.viewOriginal': 'View the original', 'chat.page': 'page {page}', 'chat.stop': '■ Stop',
    'chat.browseMemories': 'Browse its memories', 'chat.addRoundtable': 'Add to a roundtable', 'chat.insights': 'Insights',

    'mem.eyebrow': 'Memory browser', 'mem.knows': 'What {name} knows', 'mem.history': 'History', 'mem.hideHistory': 'Hide history',
    'mem.neverQuote': 'Never quote', 'mem.allowQuoting': 'Allow quoting', 'mem.neverQuoted': 'never quoted', 'mem.edit': 'Edit', 'mem.delete': 'Delete',
    'mem.recentlyDeleted': 'Recently deleted ({count})', 'mem.restore': 'Restore', 'mem.restoreVersion': 'Restore this version',
    'mem.version': 'Version {n}', 'mem.original': '(original)', 'mem.current': 'current',
  },
  hi: {
    'nav.home': 'होम', 'nav.demo': 'लाइव डेमो', 'nav.models': 'मॉडल', 'nav.create': 'बनाएँ', 'nav.roundtable': 'राउंडटेबल',
    'nav.voice': 'आवाज़', 'nav.insights': 'जानकारी', 'nav.trust': 'भरोसा', 'nav.menu': 'मेन्यू', 'nav.localTime': 'स्थानीय समय',
    'nav.close': 'बंद करें', 'nav.getStarted': 'शुरू करें', 'nav.createYourModel': 'अपना मॉडल बनाएँ', 'nav.voiceSandbox': 'आवाज़ सैंडबॉक्स',
    'nav.howItWorks': 'यह कैसे काम करता है', 'nav.roadmap': 'रोडमैप', 'nav.contact': 'संपर्क', 'nav.language': 'भाषा',

    'create.eyebrow': 'अपना मॉडल बनाएँ', 'create.building': '{name} बनाया जा रहा है', 'create.preserve': 'किसी की यादें सहेजें',
    'create.sub': 'उनके अपने शब्द, सहमति से इकट्ठा किए गए। CHRONUS केवल वही जवाब देता है जो आप यहाँ जोड़ते हैं, और हर जवाब का स्रोत दिखाता है।',
    'create.step.details': 'विवरण और सहमति', 'create.step.upload': 'दस्तावेज़ अपलोड करें', 'create.step.interview': 'साक्षात्कार', 'create.step.build': 'बनाएँ',
    'create.who': '1. यह मॉडल किसका है?', 'create.name': 'नाम', 'create.namePlaceholder': 'जैसे अम्मा, या डॉ. राव',
    'create.desc': 'छोटा परिचय (वैकल्पिक)', 'create.descPlaceholder': 'जैसे वडोदरा की सेवानिवृत्त शिक्षिका',
    'create.relationship': 'उनसे आपका रिश्ता',
    'rel.self': 'यह मैं हूँ', 'rel.family': 'परिवार का सदस्य', 'rel.friend': 'मित्र', 'rel.colleague': 'सहकर्मी', 'rel.other': 'अन्य',
    'create.memorialTitle': 'उनका निधन हो चुका है।',
    'create.memorialText': 'स्मृति मोड: जवाब याद किए गए शब्दों की तरह दिए जाते हैं, मॉडल कभी ऐसे नहीं बोलता मानो वे जीवित या मौजूद हों, और लंबी बातचीत में आराम करने की नरम याद दिलाई जाती है।',
    'create.aiTitle': 'AI आवाज़ की अनुमति दें।',
    'create.aiText': 'उनकी आवाज़ में जवाब बनाने के लिए इन यादों के छोटे अंश एक क्लाउड AI सेवा (OpenRouter) को भेजे जाते हैं। सब कुछ इसी कंप्यूटर पर रखने के लिए इसे बंद रखें; तब मॉडल शब्दशः उद्धरणों से जवाब देता है।',
    'create.consentTitle': 'सहमति।', 'create.staysHere': 'सब कुछ इसी CHRONUS में रहता है। आप बाद में सब मिटा सकते हैं।',
    'create.createModel': 'मॉडल बनाएँ', 'create.creating': 'बनाया जा रहा है…',
    'create.buildTitle': '4. बनाएँ', 'create.memoriesSoFar': 'अब तक {count} यादें ({needed} चाहिए)।',
    'create.ready': 'मॉडल तैयार है। नए दस्तावेज़ और जवाब तुरंत जुड़ जाते हैं।',
    'create.notReady': 'यादें जोड़ते ही सहेज ली जाती हैं; "बनाएँ" जाँचता है कि जवाब देने के लिए काफ़ी हैं।',
    'create.buildModel': 'मॉडल बनाएँ', 'create.buildingNow': 'बनाया जा रहा है…', 'create.chatWith': '{name} से बात करें',
    'create.voiceTitle': '5. आवाज़', 'create.optional': 'वैकल्पिक',
    'create.voiceIntro': '{name} की 6 से 60 सेकंड की साफ़ रिकॉर्डिंग से जवाब उनकी आवाज़ में सुने जा सकते हैं। Fish Audio (एक क्लाउड सेवा) इससे एक निजी आवाज़ बनाती है; आवाज़ या मॉडल हटाने पर वह वहाँ से और यहाँ से मिट जाती है।',
    'create.voiceConsentTitle': 'आवाज़ की सहमति।', 'create.cloudTitle': 'क्लाउड प्रोसेसिंग।',
    'create.cloudText': 'मैं सहमत हूँ कि आवाज़ बनाने और चलाने के लिए रिकॉर्डिंग और हर चलाए गए जवाब का पाठ Fish Audio को भेजा जाए।',
    'create.chooseRecording': 'रिकॉर्डिंग चुनें', 'create.makingVoice': 'आवाज़ बनाई जा रही है…', 'create.removeVoice': 'आवाज़ हटाएँ',
    'create.voiceAdded': 'आवाज़ जोड़ी गई', 'create.reviewMemories': 'इसकी यादें देखें या सुधारें →', 'create.seeQuestions': 'लोग इससे क्या पूछते हैं →',

    'consent.title': 'सहमति और निजता',
    'consent.intro': 'सहमति बदल सकती है। जिसने सहमति दी, या उनका परिवार, इस मॉडल को रोक सकता है, हर साल सहमति नवीनीकृत कर सकता है, कुछ विषय निजी रख सकता है, या सहमति वापस ले सकता है, जिससे सब कुछ मिट जाता है।',
    'consent.active': 'सक्रिय। सहमति की समीक्षा {date} तक होनी है।', 'consent.aYear': 'सहमति देने के एक साल बाद',
    'consent.due': 'सहमति की समीक्षा {date} को होनी थी, इसलिए नवीनीकरण तक कोई {name} से बात नहीं कर सकता।',
    'consent.paused': 'रुका हुआ: फिर से शुरू होने तक कोई {name} से बात नहीं कर सकता।',
    'consent.pause': 'रोकें', 'consent.resume': 'फिर शुरू करें', 'consent.renew': 'एक साल के लिए सहमति नवीनीकृत करें', 'consent.revoke': 'सहमति वापस लें',
    'consent.revokeConfirm': '{name} के लिए सहमति वापस लें? इससे मॉडल और उसमें सब कुछ मिट जाएगा: यादें, दस्तावेज़, साक्षात्कार के जवाब और आवाज़। इसे वापस नहीं लाया जा सकता।',
    'consent.topicsLabel': 'वर्जित विषय (अल्पविराम से अलग करें)। इनके बारे में सवालों का जवाब नहीं दिया जाता, और इनका ज़िक्र करने वाली यादें कभी उद्धृत नहीं की जातीं।',
    'consent.topicsPlaceholder': 'जैसे तलाक, अस्पताल', 'consent.saveTopics': 'विषय सहेजें', 'consent.saved': '✓ सहेजा गया',
    'consent.neverQuoteHint': 'किसी याद को रखना पर कभी उद्धृत न करना हो, तो यादें देखते समय “कभी उद्धृत न करें” चुनें।',

    'chat.ask': '{name} से कुछ भी पूछें...', 'chat.aiVoice': 'AI आवाज़', 'chat.quotesOnly': 'केवल उद्धरण', 'chat.sources': 'स्रोत',
    'chat.viewInContext': 'संदर्भ में देखें', 'chat.watchAt': '{at} से देखें', 'chat.viewPost': 'पोस्ट देखें', 'chat.openSource': 'स्रोत खोलें',
    'chat.quoting': 'उद्धृत करते हुए', 'chat.replyingTo': 'जवाब में', 'chat.aPost': 'एक पोस्ट',
    'chat.speakerNote': 'इस प्रतिलेख में बोलने वालों के नाम नहीं हैं, इसलिए साक्षात्कारकर्ता के शब्द भी मिले हो सकते हैं।',
    'chat.playOriginal': '▶ मूल रिकॉर्डिंग सुनें', 'chat.viewOriginal': 'मूल देखें', 'chat.page': 'पृष्ठ {page}', 'chat.stop': '■ रोकें',
    'chat.browseMemories': 'इसकी यादें देखें', 'chat.addRoundtable': 'राउंडटेबल में जोड़ें', 'chat.insights': 'जानकारी',

    'mem.eyebrow': 'याद-संग्रह', 'mem.knows': '{name} क्या जानते हैं', 'mem.history': 'इतिहास', 'mem.hideHistory': 'इतिहास छिपाएँ',
    'mem.neverQuote': 'कभी उद्धृत न करें', 'mem.allowQuoting': 'उद्धरण की अनुमति दें', 'mem.neverQuoted': 'कभी उद्धृत नहीं', 'mem.edit': 'सुधारें', 'mem.delete': 'मिटाएँ',
    'mem.recentlyDeleted': 'हाल में मिटाई गईं ({count})', 'mem.restore': 'वापस लाएँ', 'mem.restoreVersion': 'यह संस्करण वापस लाएँ',
    'mem.version': 'संस्करण {n}', 'mem.original': '(मूल)', 'mem.current': 'वर्तमान',
  },
  gu: {
    'nav.home': 'હોમ', 'nav.demo': 'લાઇવ ડેમો', 'nav.models': 'મોડેલ', 'nav.create': 'બનાવો', 'nav.roundtable': 'રાઉન્ડટેબલ',
    'nav.voice': 'અવાજ', 'nav.insights': 'માહિતી', 'nav.trust': 'વિશ્વાસ', 'nav.menu': 'મેનુ', 'nav.localTime': 'સ્થાનિક સમય',
    'nav.close': 'બંધ કરો', 'nav.getStarted': 'શરૂ કરો', 'nav.createYourModel': 'તમારું મોડેલ બનાવો', 'nav.voiceSandbox': 'અવાજ સેન્ડબોક્સ',
    'nav.howItWorks': 'તે કેવી રીતે કામ કરે છે', 'nav.roadmap': 'રોડમેપ', 'nav.contact': 'સંપર્ક', 'nav.language': 'ભાષા',

    'create.eyebrow': 'તમારું મોડેલ બનાવો', 'create.building': '{name} બની રહ્યું છે', 'create.preserve': 'કોઈની યાદો સાચવો',
    'create.sub': 'તેમના પોતાના શબ્દો, સંમતિથી એકઠા કરેલા. CHRONUS ફક્ત તમે અહીં ઉમેરો તેમાંથી જ જવાબ આપે છે, અને દરેક જવાબનો સ્રોત બતાવે છે.',
    'create.step.details': 'વિગતો અને સંમતિ', 'create.step.upload': 'દસ્તાવેજો અપલોડ કરો', 'create.step.interview': 'મુલાકાત', 'create.step.build': 'બનાવો',
    'create.who': '1. આ મોડેલ કોનું છે?', 'create.name': 'નામ', 'create.namePlaceholder': 'જેમ કે અમ્મા, અથવા ડૉ. રાવ',
    'create.desc': 'ટૂંકો પરિચય (વૈકલ્પિક)', 'create.descPlaceholder': 'જેમ કે વડોદરાના નિવૃત્ત શિક્ષિકા',
    'create.relationship': 'તેમની સાથે તમારો સંબંધ',
    'rel.self': 'આ હું છું', 'rel.family': 'પરિવારના સભ્ય', 'rel.friend': 'મિત્ર', 'rel.colleague': 'સહકર્મી', 'rel.other': 'અન્ય',
    'create.memorialTitle': 'તેમનું અવસાન થયું છે.',
    'create.memorialText': 'સ્મૃતિ મોડ: જવાબો યાદ કરેલા શબ્દો તરીકે અપાય છે, મોડેલ ક્યારેય એવું નથી બોલતું કે જાણે તેઓ જીવંત કે હાજર હોય, અને લાંબી વાતચીતમાં આરામ કરવાની નમ્ર યાદ અપાય છે.',
    'create.aiTitle': 'AI અવાજની મંજૂરી આપો.',
    'create.aiText': 'તેમના અવાજમાં જવાબ ઘડવા માટે આ યાદોના નાના અંશો એક ક્લાઉડ AI સેવા (OpenRouter) ને મોકલાય છે. બધું આ જ કમ્પ્યુટર પર રાખવા માટે આ બંધ રાખો; ત્યારે મોડેલ શબ્દશઃ અવતરણોથી જવાબ આપે છે.',
    'create.consentTitle': 'સંમતિ.', 'create.staysHere': 'બધું આ જ CHRONUS માં રહે છે. તમે પછીથી બધું ભૂંસી શકો છો.',
    'create.createModel': 'મોડેલ બનાવો', 'create.creating': 'બની રહ્યું છે…',
    'create.buildTitle': '4. બનાવો', 'create.memoriesSoFar': 'અત્યાર સુધી {count} યાદો ({needed} જોઈએ).',
    'create.ready': 'મોડેલ તૈયાર છે. નવા દસ્તાવેજો અને જવાબો તરત ઉમેરાય છે.',
    'create.notReady': 'યાદો ઉમેરતાં જ સચવાય છે; "બનાવો" તપાસે છે કે જવાબ આપવા માટે પૂરતી છે.',
    'create.buildModel': 'મોડેલ બનાવો', 'create.buildingNow': 'બની રહ્યું છે…', 'create.chatWith': '{name} સાથે વાત કરો',
    'create.voiceTitle': '5. અવાજ', 'create.optional': 'વૈકલ્પિક',
    'create.voiceIntro': '{name} ના 6 થી 60 સેકન્ડના સ્પષ્ટ રેકોર્ડિંગથી જવાબો તેમના અવાજમાં સાંભળી શકાય છે. Fish Audio (એક ક્લાઉડ સેવા) તેમાંથી ખાનગી અવાજ બનાવે છે; અવાજ કે મોડેલ દૂર કરવાથી તે ત્યાંથી અને અહીંથી ભૂંસાઈ જાય છે.',
    'create.voiceConsentTitle': 'અવાજની સંમતિ.', 'create.cloudTitle': 'ક્લાઉડ પ્રક્રિયા.',
    'create.cloudText': 'હું સંમત છું કે અવાજ બનાવવા અને વાપરવા માટે રેકોર્ડિંગ અને દરેક વગાડેલા જવાબનું લખાણ Fish Audio ને મોકલાય.',
    'create.chooseRecording': 'રેકોર્ડિંગ પસંદ કરો', 'create.makingVoice': 'અવાજ બની રહ્યો છે…', 'create.removeVoice': 'અવાજ દૂર કરો',
    'create.voiceAdded': 'અવાજ ઉમેરાયો', 'create.reviewMemories': 'તેની યાદો જુઓ અથવા સુધારો →', 'create.seeQuestions': 'લોકો તેને શું પૂછે છે →',

    'consent.title': 'સંમતિ અને ગોપનીયતા',
    'consent.intro': 'સંમતિ બદલાઈ શકે છે. જેમણે સંમતિ આપી, અથવા તેમનો પરિવાર, આ મોડેલને અટકાવી શકે, દર વર્ષે સંમતિ નવીકરણ કરી શકે, અમુક વિષયો ખાનગી રાખી શકે, અથવા સંમતિ પાછી ખેંચી શકે, જેનાથી બધું ભૂંસાઈ જાય છે.',
    'consent.active': 'સક્રિય. સંમતિની સમીક્ષા {date} સુધીમાં કરવાની છે.', 'consent.aYear': 'સંમતિ આપ્યાના એક વર્ષ પછી',
    'consent.due': 'સંમતિની સમીક્ષા {date} ના રોજ કરવાની હતી, તેથી નવીકરણ સુધી કોઈ {name} સાથે વાત કરી શકતું નથી.',
    'consent.paused': 'અટકાવેલું: ફરી શરૂ ન થાય ત્યાં સુધી કોઈ {name} સાથે વાત કરી શકતું નથી.',
    'consent.pause': 'અટકાવો', 'consent.resume': 'ફરી શરૂ કરો', 'consent.renew': 'એક વર્ષ માટે સંમતિ નવીકરણ કરો', 'consent.revoke': 'સંમતિ પાછી ખેંચો',
    'consent.revokeConfirm': '{name} માટે સંમતિ પાછી ખેંચવી છે? આનાથી મોડેલ અને તેમાંનું બધું ભૂંસાઈ જશે: યાદો, દસ્તાવેજો, મુલાકાતના જવાબો અને અવાજ. તે પાછું લાવી શકાશે નહીં.',
    'consent.topicsLabel': 'પ્રતિબંધિત વિષયો (અલ્પવિરામથી અલગ કરો). તેમના વિશેના પ્રશ્નોનો જવાબ અપાતો નથી, અને તેમનો ઉલ્લેખ કરતી યાદો ક્યારેય ટાંકવામાં આવતી નથી.',
    'consent.topicsPlaceholder': 'જેમ કે છૂટાછેડા, હોસ્પિટલ', 'consent.saveTopics': 'વિષયો સાચવો', 'consent.saved': '✓ સાચવ્યું',
    'consent.neverQuoteHint': 'કોઈ યાદ રાખવી હોય પણ ક્યારેય ટાંકવી ન હોય, તો યાદો જોતી વખતે “ક્યારેય ન ટાંકો” પસંદ કરો.',

    'chat.ask': '{name} ને કંઈ પણ પૂછો...', 'chat.aiVoice': 'AI અવાજ', 'chat.quotesOnly': 'ફક્ત અવતરણો', 'chat.sources': 'સ્રોતો',
    'chat.viewInContext': 'સંદર્ભમાં જુઓ', 'chat.watchAt': '{at} થી જુઓ', 'chat.viewPost': 'પોસ્ટ જુઓ', 'chat.openSource': 'સ્રોત ખોલો',
    'chat.quoting': 'ટાંકીને', 'chat.replyingTo': 'જવાબમાં', 'chat.aPost': 'એક પોસ્ટ',
    'chat.speakerNote': 'આ લખાણમાં બોલનારાઓના નામ નથી, તેથી મુલાકાત લેનારના શબ્દો પણ ભળેલા હોઈ શકે.',
    'chat.playOriginal': '▶ મૂળ રેકોર્ડિંગ સાંભળો', 'chat.viewOriginal': 'મૂળ જુઓ', 'chat.page': 'પાનું {page}', 'chat.stop': '■ બંધ કરો',
    'chat.browseMemories': 'તેની યાદો જુઓ', 'chat.addRoundtable': 'રાઉન્ડટેબલમાં ઉમેરો', 'chat.insights': 'માહિતી',

    'mem.eyebrow': 'યાદ-સંગ્રહ', 'mem.knows': '{name} શું જાણે છે', 'mem.history': 'ઇતિહાસ', 'mem.hideHistory': 'ઇતિહાસ છુપાવો',
    'mem.neverQuote': 'ક્યારેય ન ટાંકો', 'mem.allowQuoting': 'ટાંકવાની મંજૂરી આપો', 'mem.neverQuoted': 'ક્યારેય ટાંકેલું નથી', 'mem.edit': 'સુધારો', 'mem.delete': 'ભૂંસો',
    'mem.recentlyDeleted': 'તાજેતરમાં ભૂંસેલી ({count})', 'mem.restore': 'પાછી લાવો', 'mem.restoreVersion': 'આ આવૃત્તિ પાછી લાવો',
    'mem.version': 'આવૃત્તિ {n}', 'mem.original': '(મૂળ)', 'mem.current': 'હાલની',
  },
}

export const STRING_SOURCES = { CORE, HOME, PAGES, CHAT }
const STRINGS = Object.fromEntries(LANGUAGES.map(([code]) => [code, Object.assign({}, ...Object.values(STRING_SOURCES).map(s => s[code]))]))

function stored() {
  try {
    const value = window.localStorage.getItem(KEY)
    return LANGUAGES.some(([code]) => code === value) ? value : 'en'
  } catch {
    return 'en'
  }
}

const LanguageContext = createContext({ lang: 'en', setLang: () => {} })

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(stored)
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const value = useMemo(() => ({
    lang,
    setLang: (next) => {
      setLangState(next)
      try { window.localStorage.setItem(KEY, next) } catch { /* private window: this visit only */ }
    },
  }), [lang])
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function translate(lang, key, vars = {}) {
  const text = STRINGS[lang]?.[key] ?? STRINGS.en[key] ?? key
  return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? `{${name}}`))
}

export function useLanguage() {
  return useContext(LanguageContext)
}

// t('create.chatWith', { name }) in the chosen language (English when a string is missing).
// t.label('mode', d.mode): the name of a value from the server, or the value itself if it has none.
export function useT() {
  const { lang } = useContext(LanguageContext)
  return useMemo(() => {
    const t = (key, vars) => translate(lang, key, vars)
    t.label = (group, value) => (STRINGS.en[`${group}.${value}`] ? translate(lang, `${group}.${value}`) : value)
    return t
  }, [lang])
}

export function LanguagePicker() {
  const { lang, setLang } = useLanguage()
  return (
    <select className="lang-picker" value={lang} onChange={e => setLang(e.target.value)} aria-label={translate(lang, 'nav.language')}>
      {LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
    </select>
  )
}

export const STRING_KEYS = Object.keys(STRINGS.en)
export const LANGUAGE_STRINGS = STRINGS
