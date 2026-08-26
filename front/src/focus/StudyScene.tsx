export default function StudyScene() {
  return (
    <svg
      viewBox="0 0 640 360"
      className="h-auto w-full"
      role="img"
      aria-label="Study scene"
    >
      <defs>
        <linearGradient id="night" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#14101c" />
          <stop offset="100%" stopColor="#0a090d" />
        </linearGradient>
        <linearGradient id="window" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1d2a44" />
          <stop offset="100%" stopColor="#121826" />
        </linearGradient>
        <radialGradient id="lamp" cx="50%" cy="20%" r="70%">
          <stop offset="0%" stopColor="#f5d38a" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#f5d38a" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="640" height="360" fill="url(#night)" />
      <circle cx="430" cy="80" r="160" fill="url(#lamp)" />

      <rect x="48" y="36" width="210" height="168" rx="8" fill="#1a1622" />
      <rect x="60" y="48" width="186" height="144" rx="4" fill="url(#window)" />
      <line
        className="cadence-rain"
        x1="88"
        y1="56"
        x2="74"
        y2="180"
        stroke="#8ea4c8"
        strokeOpacity="0.45"
        strokeWidth="1.4"
      />
      <line
        className="cadence-rain cadence-rain-delay"
        x1="128"
        y1="52"
        x2="112"
        y2="184"
        stroke="#8ea4c8"
        strokeOpacity="0.35"
        strokeWidth="1.2"
      />
      <line
        className="cadence-rain"
        x1="168"
        y1="60"
        x2="154"
        y2="182"
        stroke="#8ea4c8"
        strokeOpacity="0.4"
        strokeWidth="1.3"
      />
      <line
        className="cadence-rain cadence-rain-delay"
        x1="208"
        y1="54"
        x2="196"
        y2="178"
        stroke="#8ea4c8"
        strokeOpacity="0.3"
        strokeWidth="1.1"
      />
      <circle cx="210" cy="78" r="16" fill="#d7c7a2" opacity="0.35" />

      <rect x="28" y="248" width="584" height="18" rx="3" fill="#2a2433" />
      <rect x="72" y="266" width="496" height="72" fill="#1c1822" />

      <rect x="118" y="198" width="168" height="52" rx="6" fill="#2f2938" />
      <rect x="130" y="208" width="92" height="10" rx="2" fill="#c4b8a4" />
      <rect x="130" y="224" width="64" height="6" rx="2" fill="#8a7f72" />

      <g className="cadence-steam" transform="translate(318 186)">
        <path
          d="M0 28 C -4 18, 4 12, 0 4"
          fill="none"
          stroke="#ece6da"
          strokeOpacity="0.45"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M8 28 C 4 20, 12 14, 8 6"
          fill="none"
          stroke="#ece6da"
          strokeOpacity="0.3"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
      <ellipse cx="326" cy="232" rx="22" ry="8" fill="#3a3344" />
      <path d="M308 232 h36 v-16 a18 18 0 0 0 -36 0 z" fill="#d7c4a6" />
      <rect x="338" y="214" width="10" height="4" rx="2" fill="#d7c4a6" />

      <g transform="translate(430 168)">
        <rect x="0" y="28" width="86" height="54" rx="8" fill="#2b3348" />
        <rect x="10" y="38" width="66" height="34" rx="3" fill="#9ad7c2" opacity="0.35" />
        <rect x="18" y="46" width="28" height="4" rx="1" fill="#d7ece4" opacity="0.6" />
        <rect x="18" y="56" width="42" height="4" rx="1" fill="#d7ece4" opacity="0.35" />
      </g>

      <g className="cadence-blink" transform="translate(250 214)">
        <ellipse cx="36" cy="28" rx="38" ry="22" fill="#e8d5b5" />
        <circle cx="18" cy="8" r="8" fill="#e8d5b5" />
        <circle cx="48" cy="6" r="7" fill="#e8d5b5" />
        <circle cx="18" cy="7" r="3.2" fill="#2a2118" />
        <circle cx="48" cy="5" r="3.2" fill="#2a2118" />
        <ellipse cx="33" cy="22" rx="4" ry="3" fill="#c9a07a" />
        <path
          className="cadence-tail"
          d="M72 30 C 92 18, 96 44, 80 42"
          fill="none"
          stroke="#e8d5b5"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <ellipse cx="36" cy="46" rx="16" ry="6" fill="#d7c09a" />
      </g>

      <g className="cadence-blink cadence-blink-slow" transform="translate(78 186)">
        <ellipse cx="24" cy="42" rx="20" ry="16" fill="#f0c9a8" />
        <circle cx="16" cy="28" r="7" fill="#f0c9a8" />
        <circle cx="30" cy="27" r="6.5" fill="#f0c9a8" />
        <circle cx="16" cy="28" r="2.4" fill="#2a2118" />
        <circle cx="30" cy="27" r="2.4" fill="#2a2118" />
        <path
          d="M4 48 C -8 62, 18 78, 28 64"
          fill="none"
          stroke="#f0c9a8"
          strokeWidth="7"
          strokeLinecap="round"
        />
      </g>

      <rect x="500" y="196" width="18" height="52" fill="#35523b" />
      <ellipse cx="509" cy="188" rx="28" ry="18" fill="#4f7a58" />
      <ellipse cx="528" cy="198" rx="16" ry="12" fill="#3f6848" />
    </svg>
  );
}
