import { useEffect, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, CalendarDays, MapPin, Search, Sparkles } from 'lucide-react'

const PAGE_SIZE = 10
const colors = ['#d8ed86', '#ffd3bf', '#d3e9e9', '#f7de91', '#d7d0fa', '#f2c5d3']
const dateText = (value) => value ? value.replaceAll('-', '.') : '일정 미정'

function App() {
  const [data, setData] = useState({ items: [], total: 0, total_pages: 0 })
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    fetch(`/api/festivals?page=${page}&size=${PAGE_SIZE}`)
      .then(async (response) => { if (!response.ok) throw new Error('축제 정보를 불러오지 못했습니다. 백엔드 서버를 확인해 주세요.'); return response.json() })
      .then((result) => { if (active) { setData(result); setError('') } })
      .catch((cause) => { if (active) setError(cause.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page])

  const filtered = data.items.filter((item) => `${item.name || ''} ${item.place || ''} ${item.road_address || ''}`.toLowerCase().includes(query.toLowerCase()))

  return <main className="shell">
    <header className="topbar"><a className="brand" href="#top"><span className="brand-mark">f.</span><span>festival<br/>fieldnotes</span></a><nav><a className="nav-active" href="#festivals">둘러보기</a><a href="#about">서비스 소개</a></nav><a className="top-link" href="https://www.data.go.kr/data/15013104/standard.do" target="_blank" rel="noreferrer">데이터 출처 <ArrowUpRight size={15}/></a></header>

    <section className="hero" id="top"><div className="hero-copy"><div className="eyebrow"><Sparkles size={14}/> LOCAL CULTURE, ALL YEAR ROUND</div><h1>다음 축제는<br/><span>어디로 갈까요?</span></h1><p>전국 곳곳의 축제 소식을 한곳에 모았어요.<br/>새로운 풍경과 이야기를 만나러 떠나보세요.</p><a className="hero-link" href="#festivals">축제 둘러보기 <ArrowDown size={16}/></a></div><div className="hero-art"><div className="sun"/><div className="hill hill-back"/><div className="hill hill-front"/><div className="festival-sign"><span>오늘의 여행</span><b>새로운<br/>계절을 만나다</b><i>FESTIVAL · 2026</i></div><div className="flower flower-one">✳</div><div className="flower flower-two">✿</div><div className="art-caption">LOCAL STORIES, MADE TO BE FOUND</div></div><div className="hero-index">01 <span/> 26</div></section>

    <section className="intro" id="about"><span className="section-kicker">FIND YOUR NEXT MOMENT</span><p>익숙한 동네에서 낯선 계절까지,<br/><em>축제는 여행을 시작하는 가장 좋은 핑계.</em></p><span className="intro-note">공공데이터포털 전국문화축제표준데이터<br/>분기별 갱신 · 전국 229개 제공기관</span></section>

    <section className="listing" id="festivals"><div className="section-head"><div><span className="section-kicker">THE FESTIVAL INDEX · 2026</span><h2>축제 아카이브<span className="count">{data.total.toLocaleString()}</span></h2></div><label className="search"><Search size={17}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="축제명, 장소 검색"/><kbd>↵</kbd></label></div>
      <div className="list-meta"><span>전국에서 발견한 축제</span><span>01 — {String(Math.min(page * PAGE_SIZE, data.total)).padStart(2, '0')} <i>/</i> {String(data.total).padStart(2, '0')}</span></div>
      <div className="festival-grid">{loading ? <div className="state">축제 정보를 불러오고 있어요…</div> : error ? <div className="state error">{error}<small>API 키를 설정한 뒤 동기화하면 축제 목록이 표시됩니다.</small></div> : filtered.length === 0 ? <div className="state">검색 결과가 없습니다.</div> : filtered.map((item, index) => <article className="festival-card" key={item.id} style={{'--card-color': colors[(index + (page - 1) * PAGE_SIZE) % colors.length]}}><div className="card-top"><span className="card-number">NO. {String((page - 1) * PAGE_SIZE + index + 1).padStart(2, '0')}</span><span className={`status ${item.status === '진행중' ? 'live' : ''}`}>{item.status}</span></div><h3>{item.name || '이름 없는 축제'}</h3><div className="card-place"><MapPin size={14}/>{item.place || item.road_address || '장소 정보 없음'}</div><div className="card-bottom"><span><CalendarDays size={14}/>{dateText(item.start_date)} — {dateText(item.end_date)}</span>{item.homepage && <a href={item.homepage} target="_blank" rel="noreferrer" aria-label="축제 홈페이지"><ArrowUpRight size={16}/></a>}</div></article>)}</div>
      <div className="pagination"><span>PAGE <b>{String(page).padStart(2, '0')}</b> OF {String(Math.max(data.total_pages, 1)).padStart(2, '0')}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage(page - 1)} aria-label="이전 페이지"><ArrowLeft size={17}/></button><button disabled={page >= data.total_pages || loading} onClick={() => setPage(page + 1)} aria-label="다음 페이지"><ArrowRight size={17}/></button></div></div>
    </section>
    <footer><a className="brand footer-brand" href="#top"><span className="brand-mark">f.</span><span>festival<br/>fieldnotes</span></a><span>전국문화축제표준데이터를 바탕으로 만들었습니다.</span><span>MADE FOR THE WAY OUT <span className="footer-star">✳</span></span></footer>
  </main>
}

export default App
