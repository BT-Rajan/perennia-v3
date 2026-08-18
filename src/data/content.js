// ──────────────────────────────────────────────────────────
// Central content store. In the original app this is admin-
// editable and served from the backend; here it's a plain data
// module so the same shape can later be swapped for an API call
// (see src/api/client.js) without touching any component.
// ──────────────────────────────────────────────────────────

export const BRAND = {
  name: "Perennia",
  wordmarkAr: "بيرينيا",
};

// Top-level site sections, mirrored in the header nav menu and the
// in-chat quick-access tray so both stay in sync from one place.
export const NAV = {
  en: [
    { id: "about", label: "About" },
    { id: "products", label: "Products" },
    { id: "services", label: "Services" },
    { id: "contact", label: "Contact Us" },
  ],
  ar: [
    { id: "about", label: "من نحن" },
    { id: "products", label: "المنتجات" },
    { id: "services", label: "الخدمات" },
    { id: "contact", label: "تواصل معنا" },
  ],
};

// Homepage "topic" buttons (hero-sections / hero-card-pills). Unlike
// NAV/SECTIONS above these don't navigate to a page — clicking one
// hands its `question` straight to the AI Assistant chat (see
// Hero.jsx handleTopicClick), so the button IS the entry point into
// a relevant conversation rather than a page link.
export const HOME_TOPICS = {
  en: [
    {
      id: "software-development",
      label: "Software Development",
      body: "Custom web, mobile, and enterprise software built around how your team actually works.",
      question: "I'd like to learn more about your software development services.",
    },
    {
      id: "artificial-intelligence",
      label: "Artificial Intelligence",
      body: "AI assistants, automation, and intelligent workflows tailored to your business.",
      question: "I'd like to learn more about your artificial intelligence services.",
    },
    {
      id: "digital-transformation",
      label: "Digital Transformation",
      body: "Modernizing processes and systems to help your organization move faster.",
      question: "I'd like to learn more about your digital transformation services.",
    },
    {
      id: "consulting",
      label: "Consulting",
      body: "Strategic and technical guidance to help you plan and execute with confidence.",
      question: "I'd like to learn more about your consulting services.",
    },
  ],
  ar: [
    {
      id: "software-development",
      label: "تطوير البرمجيات",
      body: "برمجيات وتطبيقات ويب وجوال وحلول مؤسسية مصممة وفق طريقة عمل فريقك.",
      question: "أرغب في معرفة المزيد عن خدمات تطوير البرمجيات لديكم.",
    },
    {
      id: "artificial-intelligence",
      label: "الذكاء الاصطناعي",
      body: "مساعدون بالذكاء الاصطناعي وأتمتة وسير عمل ذكي مصمم خصيصًا لعملك.",
      question: "أرغب في معرفة المزيد عن خدمات الذكاء الاصطناعي لديكم.",
    },
    {
      id: "digital-transformation",
      label: "التحول الرقمي",
      body: "تحديث الأنظمة والعمليات لمساعدة مؤسستك على العمل بشكل أسرع.",
      question: "أرغب في معرفة المزيد عن خدمات التحول الرقمي لديكم.",
    },
    {
      id: "consulting",
      label: "الاستشارات",
      body: "إرشاد استراتيجي وتقني يساعدك على التخطيط والتنفيذ بثقة.",
      question: "أرغب في معرفة المزيد عن الخدمات الاستشارية لديكم.",
    },
  ],
};

export const SECTIONS = {
  en: {
    about: {
      title: "About Perennia",
      body: "Perennia is an AI-powered technology and innovation company. We partner with businesses to design, build, and operate intelligent products — from first concept through to production support.",
    },
    products: {
      title: "Products",
      body: "AI assistants, automation workflows, and custom digital platforms — built on modern stacks and tuned to how your team actually works.",
    },
    services: {
      title: "Services",
      body: "Consulting, product design, and full-cycle engineering. We embed with your team or run the build end-to-end, whichever fits your roadmap.",
    },
    contact: {
      title: "Contact Us",
      body: "Ready to talk? Use \"Talk to Us\" to book time directly, or start a chat below and our assistant will connect you with the right person.",
    },
  },
  ar: {
    about: {
      title: "عن بيرينيا",
      body: "بيرينيا شركة تقنية وابتكار مدعومة بالذكاء الاصطناعي. نتعاون مع الشركات لتصميم وبناء وتشغيل منتجات ذكية — من الفكرة الأولى وحتى الدعم الإنتاجي.",
    },
    products: {
      title: "المنتجات",
      body: "مساعدون بالذكاء الاصطناعي، وأتمتة سير العمل، ومنصات رقمية مخصصة — مبنية على تقنيات حديثة ومصممة لتناسب طريقة عمل فريقك.",
    },
    services: {
      title: "الخدمات",
      body: "استشارات، وتصميم منتجات، وهندسة متكاملة. نندمج مع فريقك أو ننفذ المشروع بالكامل، وفق ما يناسب خطتك.",
    },
    contact: {
      title: "تواصل معنا",
      body: "جاهز للتحدث؟ استخدم \"تحدث إلينا\" لحجز موعد مباشرة، أو ابدأ محادثة أدناه وسيقوم مساعدنا بتوصيلك بالشخص المناسب.",
    },
  },
};

export const COPY = {
  en: {
    dir: "ltr",
    common: {
      close: "Close", back: "Back", send: "Send", quickMenu: "Quick menu",
      primaryNav: "Primary", goHome: "Go to home", assistantTyping: "Assistant is typing",
    },
    home: {
      welcome: "Welcome to Perennia",
      tagline: "Visit our V-Lounge for more",
      heroStatement: "Practical AI and digital products\nbuilt for businesses",
      taglineLine1: "Solving Today.",
      taglineLine2: "Shaping Tomorrow.",
      supportingText: "Digital products for businesses across India and the GCC.",
      examplePrompts: ["What does Perennia build?", "How can Perennia help my business?", "Explore our products"],
      hint: "Start chatting",
      langSwitch: "AR | عربي",
    },
    chat: {
      taglineLine1: "Solving Today. ",
      taglineLine2: "Shaping Tomorrow.",
      sub: "AI-POWERED TECHNOLOGY & INNOVATION",
      header: "AI Assistant",
      onlineStatus: "Online · AI Assistant",
      poweredBy: "Powered by",
      bookBtn: "Book a call",
      faqTitle: "Quick Questions",
      inputPlaceholder: "Ask Perennia AI anything…",
      welcomeMsg:
        "Hello! I'm Perennia's AI assistant. Before we get started, may I know your name? It helps us build a good relationship with you and follow up properly.",
      langSwitch: "AR | عربي",
      micLabel: "Talk",
      micLabelListening: "Listening…",
      micLabelSpeaking: "Speaking…",
      micUnsupported: "Voice input isn't supported in this browser — try Chrome or Edge, or use the text box instead.",
      micDenied: "Microphone access was blocked. Allow microphone access in your browser settings to talk to the assistant.",
      muteTts: "Mute replies",
      unmuteTts: "Unmute replies",
    },
    booking: {
      title: "Talk to Us",
      subtitle: "Pick a time that works for you — we'll confirm by email.",
      tabNew: "New Appointment",
      tabManage: "Manage Booking",
      date: "Date",
      slot: "Available times",
      slotEmpty: "Pick a date to see available times",
      name: "Name",
      email: "Email",
      phone: "Phone (optional)",
      service: "Service",
      selectService: "Choose a service…",
      minutesShort: "min",
      errPickService: "Please choose a service.",
      errRequiredQuestion: "Please answer all required questions.",
      notes: "Notes (optional)",
      cancel: "Cancel",
      confirm: "Confirm Booking",
      lookupId: "Appointment ID",
      lookupEmail: "Email used to book",
      findBtn: "Find My Appointment",
      cancelAppt: "Cancel Appointment",
      reschedule: "Reschedule",
      lookupDifferent: "Look up a different appointment",
      newDate: "New date",
      back: "Back",
      confirmNewTime: "Confirm New Time",
      successNew: (id) => `You're booked! Confirmation code: ${id}. A confirmation email is on its way.`,
      successCancel: "Your appointment has been cancelled.",
      successReschedule: (date, time) => `All set — your appointment is now on ${date} at ${time}.`,
      idPlaceholder: "PRN-XXXXXXXX",
      noAvailability: "No availability that day — try another date.",
      errPickDateSlot: "Please pick a date and time.",
      errName: "Please enter your name.",
      errEmail: "Please enter a valid email.",
      errLookupBoth: "Enter both the appointment ID and email.",
      errPickNewDateSlot: "Pick a new date and time.",
      errors: {
        slot_unavailable: "That time is no longer available — please pick another.",
        notice_window_passed: "This is too close to the appointment time to make that change.",
        not_found: "We couldn't find a matching appointment.",
        invalid_email: "Please enter a valid email.",
        invalid_name: "Please enter your name.",
        invalid_date: "That date isn't valid.",
        invalid_service: "That service isn't available anymore — please pick another.",
        invalid_question: "Something about the form didn't match — please try again.",
        missing_required_answer: "Please answer all required questions.",
        already_cancelled: "This appointment has already been cancelled.",
        booking_disabled: "Booking is currently unavailable — please check back soon.",
        generic: "Something went wrong — please try again.",
      },
    },
  },
  ar: {
    dir: "rtl",
    common: {
      close: "إغلاق", back: "رجوع", send: "إرسال", quickMenu: "قائمة سريعة",
      primaryNav: "الأساسية", goHome: "الذهاب إلى الرئيسية", assistantTyping: "المساعد يكتب",
    },
    home: {
      welcome: "مرحبا بك في بيرينيا",
      tagline: "زوروا V-Lounge الخاص بنا لمزيد من المعلومات",
      heroStatement: "حلول ذكاء اصطناعي عملية ومنتجات رقمية للأعمال",
      taglineLine1: "حلول اليوم.",
      taglineLine2: "لصناعة الغد.",
      supportingText: "منتجات رقمية للشركات في الهند ودول الخليج.",
      examplePrompts: ["ما الذي تبنيه بيرينيا؟", "كيف يمكن لبيرينيا مساعدة أعمالي؟", "استكشف منتجاتنا"],
      hint: "ابدأ المحادثة",
      langSwitch: "EN | English",
    },
    chat: {
      taglineLine1: "حلول اليوم. ",
      taglineLine2: "لصناعة الغد.",
      sub: "تقنية وابتكار مدعومان بالذكاء الاصطناعي",
      header: "المساعد الذكي",
      onlineStatus: "متصل الآن · مساعد ذكي",
      poweredBy: "بدعم من",
      bookBtn: "احجز مكالمة",
      faqTitle: "أسئلة سريعة",
      inputPlaceholder: "اسأل مساعد بيرينيا أي شيء…",
      welcomeMsg:
        "مرحباً! أنا المساعد الذكي لبيرينيا. قبل أن نبدأ، هل لي أن أعرف اسمك؟ هذا يساعدنا على بناء علاقة أفضل معك ومتابعة طلبك بشكل صحيح.",
      langSwitch: "EN | English",
      micLabel: "تحدث",
      micLabelListening: "جارٍ الاستماع…",
      micLabelSpeaking: "يتحدث الآن…",
      micUnsupported: "الإدخال الصوتي غير مدعوم في هذا المتصفح — جرّب Chrome أو Edge، أو استخدم مربع الكتابة بدلاً من ذلك.",
      micDenied: "تم حظر الوصول إلى الميكروفون. يرجى السماح بالوصول إليه من إعدادات المتصفح للتحدث مع المساعد.",
      muteTts: "كتم الردود الصوتية",
      unmuteTts: "تفعيل الردود الصوتية",
    },
    booking: {
      title: "تحدث إلينا",
      subtitle: "اختر الوقت المناسب لك — سنؤكد ذلك عبر البريد الإلكتروني.",
      tabNew: "موعد جديد",
      tabManage: "إدارة الحجز",
      date: "التاريخ",
      slot: "الأوقات المتاحة",
      slotEmpty: "اختر تاريخًا لرؤية الأوقات المتاحة",
      name: "الاسم",
      email: "البريد الإلكتروني",
      phone: "الهاتف (اختياري)",
      service: "الخدمة",
      selectService: "اختر خدمة…",
      minutesShort: "د",
      errPickService: "يرجى اختيار خدمة.",
      errRequiredQuestion: "يرجى الإجابة عن جميع الأسئلة المطلوبة.",
      notes: "ملاحظات (اختياري)",
      cancel: "إلغاء",
      confirm: "تأكيد الحجز",
      lookupId: "رقم الموعد",
      lookupEmail: "البريد الإلكتروني المستخدم للحجز",
      findBtn: "ابحث عن موعدي",
      cancelAppt: "إلغاء الموعد",
      reschedule: "إعادة الجدولة",
      lookupDifferent: "البحث عن موعد آخر",
      newDate: "تاريخ جديد",
      back: "رجوع",
      confirmNewTime: "تأكيد الوقت الجديد",
      successNew: (id) => `تم الحجز! رمز التأكيد: ${id}. بريد التأكيد في طريقه إليك.`,
      successCancel: "تم إلغاء موعدك.",
      successReschedule: (date, time) => `تم! موعدك الآن في ${date} الساعة ${time}.`,
      idPlaceholder: "PRN-XXXXXXXX",
      noAvailability: "لا توجد مواعيد متاحة في هذا اليوم — جرّب تاريخًا آخر.",
      errPickDateSlot: "يرجى اختيار تاريخ ووقت.",
      errName: "يرجى إدخال اسمك.",
      errEmail: "يرجى إدخال بريد إلكتروني صالح.",
      errLookupBoth: "أدخل رقم الموعد والبريد الإلكتروني معًا.",
      errPickNewDateSlot: "اختر تاريخًا ووقتًا جديدين.",
      errors: {
        slot_unavailable: "لم يعد هذا الوقت متاحًا — يرجى اختيار وقت آخر.",
        notice_window_passed: "الوقت المتبقي غير كافٍ لإجراء هذا التغيير.",
        not_found: "لم نتمكن من العثور على موعد مطابق.",
        invalid_email: "يرجى إدخال بريد إلكتروني صالح.",
        invalid_name: "يرجى إدخال اسمك.",
        invalid_date: "هذا التاريخ غير صالح.",
        invalid_service: "هذه الخدمة لم تعد متاحة — يرجى اختيار خدمة أخرى.",
        invalid_question: "حدث خلل في النموذج — يرجى المحاولة مرة أخرى.",
        missing_required_answer: "يرجى الإجابة عن جميع الأسئلة المطلوبة.",
        already_cancelled: "تم إلغاء هذا الموعد بالفعل.",
        booking_disabled: "الحجز غير متاح حاليًا — يرجى المحاولة لاحقًا.",
        generic: "حدث خطأ ما — يرجى المحاولة مرة أخرى.",
      },
    },
  },
};

export const FAQ = {
  en: [
    { q: "What services does Perennia offer?", a: "We build AI-powered assistants, automation, and digital products tailored to your business — from concept through to production support." },
    { q: "How can I book a consultation?", a: "Tap \"Talk to Us\" above, choose a free slot, and you'll get an instant confirmation by email — no back-and-forth required." },
    { q: "Do you support Arabic and English?", a: "Yes — the whole experience, including this assistant, works fully in both English and Arabic with proper right-to-left layout." },
    { q: "Where are you located?", a: "We work with clients globally and meet either virtually or in person — ask during booking and we'll accommodate you." },
  ],
  ar: [
    { q: "ما هي الخدمات التي تقدمها بيرينيا؟", a: "نصمم مساعدين مدعومين بالذكاء الاصطناعي وحلول أتمتة ومنتجات رقمية مخصصة لعملك — من الفكرة وحتى الدعم الإنتاجي." },
    { q: "كيف يمكنني حجز استشارة؟", a: "اضغط على \"تحدث إلينا\" أعلاه، اختر موعدًا متاحًا، وستحصل على تأكيد فوري عبر البريد الإلكتروني." },
    { q: "هل تدعمون اللغتين العربية والإنجليزية؟", a: "نعم — التجربة بأكملها، بما في ذلك هذا المساعد، تعمل بالكامل باللغتين مع تخطيط صحيح من اليمين إلى اليسار." },
    { q: "أين يقع مقركم؟", a: "نعمل مع عملاء حول العالم ونلتقي افتراضيًا أو شخصيًا — أخبرنا أثناء الحجز وسنوفر لك ما يناسبك." },
  ],
};
