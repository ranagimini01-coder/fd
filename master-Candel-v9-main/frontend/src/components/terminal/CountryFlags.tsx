import { useId } from "react";
import { getMarket, type Market } from "@/lib/markets";

function Flag({ country }: { country: string }) {
  const id = useId().replaceAll(":", "");
  return <svg viewBox="0 0 28 28" aria-hidden="true" className="country-flag">
    <defs><clipPath id={id}><circle cx="14" cy="14" r="13" /></clipPath></defs>
    <g clipPath={`url(#${id})`}>
      <rect width="28" height="28" fill="#fff" />
      {country === "us" && <><path d="M0 2h28M0 6h28M0 10h28M0 14h28M0 18h28M0 22h28M0 26h28" stroke="#e24858" strokeWidth="2" /><path d="M0 0h14v15H0z" fill="#274a8c" /><path d="M3 3h1m4 0h1m-6 4h1m4 0h1m-6 4h1m4 0h1" stroke="#fff" strokeWidth="1.5" /></>}
      {(country === "gb" || country === "au" || country === "nz") && <><rect width="28" height="28" fill="#234484" /><path d="M0 0l28 28M28 0L0 28" stroke="#fff" strokeWidth="5" /><path d="M0 0l28 28M28 0L0 28" stroke="#e64a58" strokeWidth="2" /><path d="M14 0v28M0 14h28" stroke="#fff" strokeWidth="8" /><path d="M14 0v28M0 14h28" stroke="#dc394a" strokeWidth="4" />{country !== "gb" && <><rect x="14" y="14" width="14" height="14" fill="#234484" /><path d="m21 16 1 3 3 1-3 1-1 3-1-3-3-1 3-1z" fill={country === "nz" ? "#ed5b64" : "white"} /></>}</>}
      {country === "jp" && <circle cx="14" cy="14" r="6.5" fill="#d92748" />}
      {country === "ch" && <><rect width="28" height="28" fill="#ed3a47" /><path d="M11 6h6v5h5v6h-5v5h-6v-5H6v-6h5z" fill="white" /></>}
      {country === "ca" && <><path d="M0 0h7v28H0zM21 0h7v28h-7z" fill="#e54250" /><path d="m14 6 2 5 3-1-1 4 3 1-6 4v4h-2v-4l-6-4 3-1-1-4 3 1z" fill="#e54250" /></>}
      {country === "ru" && <><path d="M0 9h28v10H0z" fill="#3274c4" /><path d="M0 19h28v9H0z" fill="#ed4856" /></>}
      {country === "br" && <><rect width="28" height="28" fill="#169258" /><path d="m14 4 12 10-12 10L2 14z" fill="#ffda56" /><circle cx="14" cy="14" r="5.5" fill="#28529e" /><path d="M9 12q5-1 10 4" stroke="#fff" fill="none" /></>}
      {country === "in" && <><path d="M0 0h28v9H0z" fill="#f4a653" /><path d="M0 19h28v9H0z" fill="#199c68" /><circle cx="14" cy="14" r="3" stroke="#274484" fill="none" /><path d="M11 14h6m-3-3v6" stroke="#274484" /></>}
      {country === "cl" && <><path d="M0 14h28v14H0z" fill="#e94454" /><path d="M0 0h14v14H0z" fill="#255493" /><path d="m7 3 1 3 3 1-3 1-1 3-1-3-3-1 3-1z" fill="white" /></>}
      {country === "eu" && <><rect width="28" height="28" fill="#2149a2" />{Array.from({ length: 12 }, (_, i) => <circle key={i} cx={14 + Math.cos(i * Math.PI / 6) * 8} cy={14 + Math.sin(i * Math.PI / 6) * 8} r="1.1" fill="#ffe177" />)}</>}
      {country === "bd" && <><rect width="28" height="28" fill="#087951" /><circle cx="13" cy="14" r="6" fill="#ee4559" /></>}
      {country === "cn" && <><rect width="28" height="28" fill="#e33c44" /><path d="m9 4 1.5 4H15l-3.5 2.5L13 15l-4-2.5L5 15l1.5-4.5L3 8h4.5z" fill="#ffda58" /></>}
      {["id","pl","ar","eg","ng","mx","th","ae"].includes(country) && <><rect width="28" height="28" fill={country === "ar" ? "#8cd0ee" : country === "ng" ? "#168d65" : "#df4451"} /><rect y={country === "id" ? 14 : 9} width="28" height={country === "id" ? 14 : 10} fill="white" />{country === "pl" && <rect width="28" height="14" fill="white" />}{country === "eg" && <rect y="19" width="28" height="9" fill="#27303e" />}{country === "th" && <rect y="9" width="28" height="10" fill="#284080" />}{country === "ng" && <rect x="9" width="10" height="28" fill="white" />}{country === "mx" && <rect width="9" height="28" fill="#1b9568" />}{country === "ae" && <><rect y="0" width="28" height="9" fill="#199c64" /><rect y="19" width="28" height="9" fill="#27303e" /><rect width="8" height="28" fill="#df4451" /></>}</>}
      {["tr","pk","dz","sa"].includes(country) && <><rect width="28" height="28" fill={country === "tr" ? "#e4454e" : "#148956"} /><circle cx="13" cy="14" r="7" fill="white" /><circle cx="16" cy="12" r="6" fill={country === "tr" ? "#e4454e" : "#148956"} /></>}
      {["se","no","dk"].includes(country) && <><rect width="28" height="28" fill={country === "se" ? "#307bb9" : "#d94455"} /><path d="M11 0v28M0 14h28" stroke={country === "se" ? "#ffdb66" : "white"} strokeWidth="5" />{country === "no" && <path d="M11 0v28M0 14h28" stroke="#24427b" strokeWidth="2.5" />}</>}
      {["sg","ph","za","kr"].includes(country) && <><rect width="28" height="14" fill={country === "ph" ? "#2667ae" : country === "za" ? "#19935e" : "#e65361"} /><circle cx="14" cy="14" r="5" fill={country === "kr" ? "#347ab7" : "#ffdd8b"} /></>}
    </g><circle cx="14" cy="14" r="13" fill="none" stroke="white" strokeOpacity=".18" />
  </svg>;
}

export default function CountryFlags({ pairId, markets = [] }: { pairId: string; markets?: readonly Pick<Market, "id" | "symbol" | "category" | "countries">[] }) {
  const market = markets.find(item => item.id === pairId) ?? getMarket(pairId);
  if (market.category !== "Currencies" && market.symbol !== "UKBrent" && market.symbol !== "Composite") return <span className={`asset-symbol asset-${market.category.toLowerCase()}`} aria-label={market.symbol}>{market.symbol === "Bitcoin" ? "₿" : market.symbol === "Gold" ? "Au" : market.symbol === "Silver" ? "Ag" : market.symbol.slice(0, 2).toUpperCase()}</span>;
  const countries = market.countries;
  return <span className="country-flags" aria-label={`${countries[0].toUpperCase()} / ${countries[1].toUpperCase()}`}><Flag country={countries[0]} /><Flag country={countries[1]} /></span>;
}