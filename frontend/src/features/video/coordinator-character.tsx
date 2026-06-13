type CoordinatorCharacterProps = {
  className?: string;
  pose?: "welcoming" | "planning" | "fundraising";
  animated?: boolean;
};

const poseCopy = {
  welcoming: "Volunteer welcome checklist",
  planning: "Saturday pantry roster",
  fundraising: "Spring gala pledges",
};

export function CoordinatorCharacter({
  className,
  pose = "planning",
  animated = true,
}: CoordinatorCharacterProps) {
  const animationClass = animated ? "coordinator-character--animated" : "";
  const eyebrow = pose === "fundraising" ? "M18 5 Q25 1 32 5" : "M18 5 Q25 3 32 5";
  const handY = pose === "welcoming" ? 180 : 192;
  const clipboardAccent = pose === "fundraising" ? "#db7a4b" : "#407c87";

  return (
    <figure className={["coordinator-character", animationClass, className].filter(Boolean).join(" ")}>
      <svg
        aria-labelledby="coordinator-character-title coordinator-character-description"
        role="img"
        viewBox="0 0 720 720"
        xmlns="http://www.w3.org/2000/svg"
      >
        <title id="coordinator-character-title">Middle-aged nonprofit coordinator character</title>
        <desc id="coordinator-character-description">
          A warm middle-aged female nonprofit coordinator holding a clipboard, surrounded by
          volunteer scheduling and fundraising event planning details.
        </desc>

        <defs>
          <linearGradient id="coordinator-bg" x1="86" x2="630" y1="70" y2="654" gradientUnits="userSpaceOnUse">
            <stop stopColor="#eef8f3" />
            <stop offset="0.52" stopColor="#f8f2e7" />
            <stop offset="1" stopColor="#e8f1fb" />
          </linearGradient>
          <linearGradient id="coordinator-blazer" x1="248" x2="490" y1="324" y2="650" gradientUnits="userSpaceOnUse">
            <stop stopColor="#356978" />
            <stop offset="1" stopColor="#234a5a" />
          </linearGradient>
          <filter id="coordinator-shadow" x="-20%" y="-20%" width="140%" height="150%">
            <feDropShadow dx="0" dy="18" floodColor="#1d2d35" floodOpacity="0.18" stdDeviation="18" />
          </filter>
        </defs>

        <rect width="720" height="720" rx="44" fill="url(#coordinator-bg)" />
        <g opacity="0.74">
          <circle cx="138" cy="135" r="44" fill="#ffffff" />
          <circle cx="595" cy="124" r="28" fill="#ffffff" />
          <circle cx="634" cy="530" r="54" fill="#ffffff" />
          <circle cx="104" cy="560" r="31" fill="#ffffff" />
        </g>

        <g className="coordinator-character__note coordinator-character__note--left">
          <rect x="76" y="205" width="142" height="130" rx="18" fill="#ffffff" stroke="#d9e2df" strokeWidth="4" />
          <rect x="100" y="230" width="70" height="10" rx="5" fill="#407c87" />
          <rect x="100" y="258" width="94" height="8" rx="4" fill="#d9e2df" />
          <rect x="100" y="281" width="74" height="8" rx="4" fill="#d9e2df" />
          <path d="M105 306 L118 318 L146 288" fill="none" stroke="#67a85b" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
        </g>

        <g className="coordinator-character__note coordinator-character__note--right">
          <rect x="510" y="195" width="145" height="132" rx="18" fill="#ffffff" stroke="#d9e2df" strokeWidth="4" />
          <rect x="535" y="222" width="92" height="10" rx="5" fill="#db7a4b" />
          <circle cx="550" cy="265" r="12" fill="#f3c05b" />
          <rect x="574" y="256" width="54" height="8" rx="4" fill="#d9e2df" />
          <circle cx="550" cy="298" r="12" fill="#f3c05b" />
          <rect x="574" y="289" width="38" height="8" rx="4" fill="#d9e2df" />
        </g>

        <g className="coordinator-character__body" filter="url(#coordinator-shadow)">
          <path d="M246 617 C258 486 258 389 320 348 C348 329 398 327 430 348 C492 389 501 486 515 617 Z" fill="url(#coordinator-blazer)" />
          <path d="M324 350 L382 523 L438 350 C408 333 357 332 324 350 Z" fill="#f7f1df" />
          <path d="M346 359 L385 458 L421 359" fill="none" stroke="#d7c7a8" strokeWidth="6" strokeLinecap="round" />
          <path d="M288 397 C235 430 201 477 178 552" fill="none" stroke="#356978" strokeWidth="42" strokeLinecap="round" />
          <path d="M484 397 C535 431 559 480 574 555" fill="none" stroke="#234a5a" strokeWidth="42" strokeLinecap="round" />
          <path d={`M179 ${handY} C195 230 222 293 212 368`} fill="none" stroke="#b96f55" strokeWidth="31" strokeLinecap="round" />
          <circle cx="177" cy={handY - 1} r="19" fill="#c77d61" />
          <path d="M572 556 C584 589 549 604 530 579" fill="none" stroke="#c77d61" strokeWidth="30" strokeLinecap="round" />
        </g>

        <g className="coordinator-character__clipboard">
          <rect x="430" y="396" width="166" height="204" rx="18" fill="#fdfcf7" stroke="#d4d5cd" strokeWidth="6" />
          <rect x="474" y="375" width="78" height="42" rx="15" fill="#2f5664" />
          <rect x="489" y="392" width="48" height="8" rx="4" fill="#fdfcf7" opacity="0.7" />
          <rect x="458" y="437" width="92" height="12" rx="6" fill={clipboardAccent} />
          <rect x="458" y="471" width="109" height="8" rx="4" fill="#d9e2df" />
          <rect x="458" y="501" width="84" height="8" rx="4" fill="#d9e2df" />
          <rect x="458" y="531" width="97" height="8" rx="4" fill="#d9e2df" />
          <path d="M464 566 L477 578 L504 548" fill="none" stroke="#67a85b" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        </g>

        <g className="coordinator-character__head">
          <path d="M279 237 C278 156 326 109 392 112 C461 115 500 169 489 246 C480 307 439 350 383 350 C324 350 286 306 279 237 Z" fill="#533d39" />
          <path d="M312 252 C295 230 292 201 312 174 C335 142 387 132 431 153 C464 168 476 199 470 239 C462 300 427 332 384 333 C344 334 320 307 312 252 Z" fill="#c77d61" />
          <path d="M316 216 C340 157 390 143 463 181 C443 124 333 102 294 176 C283 198 285 224 297 244 C302 235 308 226 316 216 Z" fill="#5f4541" />
          <path d="M298 241 C284 232 270 241 272 261 C274 281 291 292 305 282" fill="#c77d61" />
          <path d="M470 241 C486 232 499 243 496 263 C493 282 478 292 466 282" fill="#c77d61" />
          <path d="M338 254 C350 247 364 247 376 254" fill="none" stroke="#5b3d34" strokeWidth="5" strokeLinecap="round" />
          <path d="M408 254 C421 247 435 247 447 254" fill="none" stroke="#5b3d34" strokeWidth="5" strokeLinecap="round" />
          <path d="M367 290 C379 301 403 302 416 289" fill="none" stroke="#7b3b3c" strokeWidth="5" strokeLinecap="round" />
          <path d="M386 257 C381 277 381 279 392 282" fill="none" stroke="#a95f4e" strokeWidth="5" strokeLinecap="round" />
          <path d={eyebrow} transform="translate(315 224)" fill="none" stroke="#4b3430" strokeWidth="5" strokeLinecap="round" />
          <path d={eyebrow} transform="translate(384 224)" fill="none" stroke="#4b3430" strokeWidth="5" strokeLinecap="round" />
          <g opacity="0.9">
            <circle cx="357" cy="260" r="25" fill="none" stroke="#315869" strokeWidth="5" />
            <circle cx="425" cy="260" r="25" fill="none" stroke="#315869" strokeWidth="5" />
            <path d="M382 259 H400" stroke="#315869" strokeWidth="5" strokeLinecap="round" />
          </g>
          <path d="M331 149 C344 113 388 94 430 108 C475 123 503 161 505 216 C482 178 439 160 388 160 C361 160 341 157 331 149 Z" fill="#6e5350" />
          <path d="M416 119 C436 139 445 167 446 202" fill="none" stroke="#8a6a66" strokeWidth="10" strokeLinecap="round" opacity="0.62" />
        </g>

        <g className="coordinator-character__badge">
          <rect x="309" y="404" width="78" height="46" rx="8" fill="#ffffff" stroke="#d9e2df" strokeWidth="4" />
          <rect x="324" y="416" width="48" height="7" rx="3.5" fill="#407c87" />
          <rect x="324" y="432" width="36" height="6" rx="3" fill="#d9e2df" />
        </g>

        <g className="coordinator-character__calendar">
          <rect x="148" y="438" width="126" height="118" rx="16" fill="#ffffff" stroke="#d9e2df" strokeWidth="5" />
          <rect x="148" y="438" width="126" height="34" rx="16" fill="#407c87" />
          <rect x="173" y="491" width="19" height="17" rx="4" fill="#f3c05b" />
          <rect x="204" y="491" width="19" height="17" rx="4" fill="#d9e2df" />
          <rect x="235" y="491" width="19" height="17" rx="4" fill="#d9e2df" />
          <rect x="173" y="520" width="19" height="17" rx="4" fill="#d9e2df" />
          <rect x="204" y="520" width="19" height="17" rx="4" fill="#67a85b" />
          <rect x="235" y="520" width="19" height="17" rx="4" fill="#d9e2df" />
        </g>
      </svg>

      <figcaption>
        <strong>Mara Ellis</strong>
        <span>{poseCopy[pose]}</span>
      </figcaption>
    </figure>
  );
}

