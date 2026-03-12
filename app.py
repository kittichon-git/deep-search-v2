import streamlit as st
import re
import urllib.parse
from datetime import datetime
import os
import html
from dotenv import load_dotenv
load_dotenv()

# Support Streamlit Cloud (st.secrets) and local .env
def _get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, '')

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

from database import (
    get_auctions, mark_auction_as_read,
    get_search_settings, insert_search_setting, update_search_setting, delete_search_setting,
    get_global_excludes, insert_global_exclude, update_global_exclude, delete_global_exclude,
    get_province_groups, insert_province_group, update_province_group, delete_province_group
)

st.set_page_config(page_title="Auction Discovery", page_icon="📋", layout="centered")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap');
body, .block-container {{ font-family: 'Prompt', Arial, sans-serif !important; }}
.block-container {{ max-width: 760px !important; padding: 1.5rem 1.5rem !important; }}

.summary-bar {{ font-size:0.87rem; color:#70757a; margin-bottom:20px; padding:8px 12px; background:#f8f9fa; border-radius:6px; }}

.result-item {{ margin-bottom: 24px; position:relative; }}
.result-site  {{ font-size:0.85rem; color:#202124; margin-bottom:2px; }}
.result-title a {{ font-size:1.25rem; color:#1a0dab; text-decoration:none; font-weight:400; line-height:1.3; }}
.result-title a:hover {{ text-decoration:underline; }}

.is-read-item a {{ color:#70757a !important; text-decoration: line-through !important; }}
.is-read-item .result-snippet {{ opacity:0.5 !important; }}

.result-meta  {{ font-size:0.75rem; color:#70757a; margin:4px 0 2px 0; }}
.result-snippet {{ font-size:0.88rem; color:#4d5156; line-height:1.58; transition: opacity 0.3s; }}
.hl {{ font-weight:700; color:#c5221f; }}
.s-tag {{ display:inline-block !important; font-size:0.68rem; background:#e8f0fe; border:1px solid #c5cfe8; color:#174ea6; border-radius:4px; padding:2px 6px; margin-right:3px; max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; vertical-align:middle; cursor:help; }}
.t-tag {{ background:#e6f4ea; border-color:#b7dfba; color:#137333; }}
.d-tag {{ background:#fef7e0; border-color:#fbe4a0; color:#b06000; }}
.divider {{ border:none; border-top:1px solid #e8eaed; margin:10px 0; }}

/* Button styling */
div[data-testid="stButton"] button {{
    border-radius: 50% !important; width:36px !important; height:36px !important;
    padding:0 !important; font-size:1.1rem !important;
    background: transparent !important; border: 1px solid #dadce0 !important; color: #dadce0 !important;
}}
div[data-testid="stButton"] button:hover {{
    border-color: #4caf50 !important; color: #4caf50 !important; background: #e8f5e9 !important;
}}
</style>

<script>
window.trackClick = function(id) {{
    const url = "{SUPABASE_URL}/rest/v1/auctions?id=eq." + id;
    fetch(url, {{
        method: 'PATCH',
        keepalive: true,
        headers: {{
            'apikey': "{SUPABASE_KEY}",
            'Authorization': 'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }},
        body: JSON.stringify({{ is_read: true }})
    }}).catch(err => console.error('Sync error:', err));
}};

document.addEventListener('click', function(e) {{
    const link = e.target.closest('a.track-link');
    if (link) {{
        const id = link.getAttribute('data-id');
        window.trackClick(id);
        
        const item = link.closest('.result-item');
        if (item) {{
            item.classList.add('is-read-item');
            const a = item.querySelector('.result-title a');
            if(a) {{
                a.style.color = '#70757a';
                a.style.textDecoration = 'line-through';
            }}
            const snip = item.querySelector('.result-snippet');
            if(snip) snip.style.opacity = '0.5';
        }}
    }}
}});
</script>
""", unsafe_allow_html=True)

HIGHLIGHT_WORDS = ['ขายทอดตลาด','ชำรุด','เสื่อมสภาพ','ไม่จำเป็นต้องใช้ในราชการ','พัสดุ','ครุภัณฑ์','จำหน่าย','รื้อถอน','ซากยานยนต์']
THAI_MONTHS = ['','มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม']

def thai_dt(s):
    if not s: return '-'
    try:
        dt = datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return f"{dt.day} {THAI_MONTHS[dt.month]} {dt.year+543}  {dt.hour:02d}.{dt.minute:02d} น."
    except: return str(s)[:16]

def hl(text):
    if not text: return ''
    for w in HIGHLIGHT_WORDS:
        text = re.compile(f"({re.escape(w)})", re.I).sub(r'<span class="hl">\1</span>', str(text))
    return text

def domain(url):
    try: return url.split('/')[2].replace('www.','')
    except: return url[:40]

def tfl(tf): return {'1d':'1 วัน','7d':'7 วัน','any':'ตลอดเวลา'}.get(tf or '',tf or '')

def mark_and_rerun(auction_id):
    mark_auction_as_read(auction_id)

import html as _html
import streamlit.components.v1 as components

def shorten_url(url, max_len=80):
    return url[:max_len - 3] + '...' if url and len(url) > max_len else (url or '')

_ITEM_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap');
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Prompt', Arial, sans-serif; background: transparent; padding: 2px 0; }

.ri { padding: 2px 0 6px 0; }

.site {
  font-size: 0.82rem;
  color: #3c4043;
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.site small { color: #9aa0a6; font-size: 0.75rem; }

.title a {
  font-size: 1.15rem;
  color: #1a0dab;
  text-decoration: none;
  font-weight: 400;
  line-height: 1.4;
  display: inline-block;
  margin-bottom: 2px;
}
.title a:hover { text-decoration: underline; }
.title.read a {
  color: #9e9e9e !important;
  text-decoration: line-through !important;
}

.meta {
  margin: 5px 0 5px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.tag {
  display: inline-block;
  font-size: 0.68rem;
  border-radius: 4px;
  padding: 2px 7px;
  border: 1px solid;
  vertical-align: middle;
  white-space: nowrap;
  font-family: 'Prompt', Arial, sans-serif;
}
.st {
  background: #e8f0fe;
  border-color: #c5cfe8;
  color: #174ea6;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: help;
}
.tt { background: #e6f4ea; border-color: #b7dfba; color: #137333; }
.dt { background: #fef7e0; border-color: #fbe4a0; color: #b06000; }

.snippet {
  font-size: 0.875rem;
  color: #4d5156;
  line-height: 1.62;
  margin-top: 2px;
  transition: opacity 0.3s;
}
.snippet.read { opacity: 0.45; }

.hl { font-weight: 700; color: #c5221f; }
</style>"""

def render_item(item, idx, is_read=False):
    link   = item.get('link','#')
    aid    = str(item.get('id',''))
    st_tag = item.get('search_term','') or ''
    tf_tag = tfl(item.get('time_filter','') or '')
    found  = thai_dt(item.get('found_at',''))

    title_hl = hl(_html.escape(item.get('title','')))
    snip_hl  = hl(_html.escape(item.get('snippet','—')))
    safe_t   = _html.escape(st_tag, quote=True)
    short_t  = _html.escape(st_tag[:28]) + ("…" if len(st_tag)>28 else "")
    short_u  = _html.escape(shorten_url(link, 70))
    dom_str  = _html.escape(domain(link))
    link_esc = _html.escape(link)
    read_cls = "read" if is_read else ""

    tf_span = f'<span class="tag tt">⏱ {_html.escape(tf_tag)}</span>' if tf_tag else ''
    dt_span = f'<span class="tag dt">📅 {_html.escape(found)}</span>'
    te_span = f'<span class="tag st" title="{safe_t}">{short_t}</span>' if st_tag else ''

    html_src = f"""{_ITEM_CSS}
<div class="ri">
  <div class="site">🌐 {dom_str} — <small style="color:#9aa0a6">{short_u}</small></div>
  <div class="title {read_cls}">
    <a id="a{aid}" href="{link_esc}" target="_blank"
       onclick="markRead('{aid}'); return true;">
      {idx}. {title_hl}
    </a>
  </div>
  <div class="meta">{te_span}{tf_span}{dt_span}</div>
  <div class="snippet {read_cls}" id="s{aid}">{snip_hl}</div>
</div>
<script>
function markRead(id){{
  var a=document.getElementById('a'+id);
  var s=document.getElementById('s'+id);
  if(a){{a.style.color='#70757a';a.style.textDecoration='line-through';}}
  if(s){{s.style.opacity='0.5';}}
  fetch('{SUPABASE_URL}/rest/v1/auctions?id=eq.'+id,{{
    method:'PATCH',keepalive:true,
    headers:{{'apikey':'{SUPABASE_KEY}','Authorization':'Bearer {SUPABASE_KEY}',
             'Content-Type':'application/json','Prefer':'return=minimal'}},
    body:JSON.stringify({{is_read:true}})
  }});
}}
</script>"""

    # Calculate dynamic height
    title_len  = len(item.get('title',''))
    snip_len   = len(item.get('snippet',''))
    h = 48                          # base: site + title (1 line)
    h += max(1, title_len // 45) * 30   # extra lines for long titles
    h += 22                         # meta row (tags)
    h += max(2, snip_len // 60) * 22    # snippet lines
    h += 14                         # padding

    col_body, col_btn = st.columns([11, 1])
    with col_body:
        components.html(html_src, height=h, scrolling=False)
    with col_btn:
        st.markdown(f'<div style="height:{max(h-30,40)}px;display:flex;align-items:center;justify-content:center">', unsafe_allow_html=True)
        if not is_read:
            if st.button("✓", key=f"chk_{aid}", help="ทำเครื่องหมายว่าอ่านแล้ว"):
                mark_and_rerun(aid)
                st.rerun()
        else:
            st.markdown('<div style="color:#34a853;font-size:1.4rem;text-align:center;font-weight:bold">✓</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #e8eaed;margin:2px 0 12px 0">', unsafe_allow_html=True)


# ── SETTINGS HELPERS ──────────────────────────────────────
def get_exclude_group_names(excludes):
    return sorted(set(e.get('group_name','ค่าเริ่มต้น') for e in excludes))

def settings_tab(settings, all_excludes, province_groups):
    st.subheader("🔍 ชุดคำค้นหา (Query Templates)")
    
    exclude_group_names = get_exclude_group_names(all_excludes)
    
    for s in settings:
        with st.expander(f"📝 {s['template'][:70]}{'…' if len(s['template'])>70 else ''}", expanded=False):
            edit_key = f"edit_{s['id']}"
            if st.session_state.get(edit_key):
                new_tpl = st.text_area("Template", value=s['template'], key=f"tpl_edit_{s['id']}", height=80)
                new_tfs = st.multiselect("โหมดเวลา", ["1d","7d","any"], default=s.get('time_filters',[]), key=f"tf_edit_{s['id']}")
                new_exc_groups = st.multiselect("ใช้กลุ่มคำยกเว้น", exclude_group_names, default=s.get('exclude_groups',[]) or [], key=f"eg_edit_{s['id']}")
                c1, c2, c3 = st.columns([1,1,3])
                with c1:
                    if st.button("💾 บันทึก", key=f"save_{s['id']}"):
                        update_search_setting(s['id'], new_tpl, new_tfs, new_exc_groups)
                        st.session_state[edit_key] = False
                        st.rerun()
                with c2:
                    if st.button("↩️ ยกเลิก", key=f"cancel_{s['id']}"):
                        st.session_state[edit_key] = False
                        st.rerun()
                with c3:
                    if st.button("🗑️ ลบ", key=f"del_{s['id']}", type="secondary"):
                        delete_search_setting(s['id']); st.rerun()
            else:
                st.caption(f"**เวลา:** {', '.join(s.get('time_filters',[]))} | **กลุ่มยกเว้น:** {', '.join(s.get('exclude_groups',[]) or []) or '—'}")
                if st.button("✏️ แก้ไข", key=f"edit_btn_{s['id']}"):
                    st.session_state[edit_key] = True; st.rerun()

    with st.expander("➕ เพิ่มชุดคำค้นหาใหม่"):
        with st.form("add_setting"):
            tpl = st.text_area("Template", placeholder='"ขายทอดตลาด" ("พัสดุ" OR "ครุภัณฑ์") ${YEAR_ANCHOR}', height=80)
            tfs = st.multiselect("โหมดเวลา", ["1d","7d","any"], default=["any"])
            exc_g = st.multiselect("ใช้กลุ่มคำยกเว้น", exclude_group_names)
            if st.form_submit_button("💾 บันทึก") and tpl:
                insert_search_setting(tpl, tfs, exc_g); st.success("เพิ่มสำเร็จ!"); st.rerun()

    st.markdown("---")

    # ── Exclude Groups ──
    st.subheader("🚫 กลุ่มคำยกเว้น (Exclude Groups)")
    for grp_name in exclude_group_names:
        group_items = [e for e in all_excludes if e.get('group_name') == grp_name]
        with st.expander(f"📌 กลุ่ม: {grp_name} ({len(group_items)} รายการ)"):
            for exc in group_items:
                eg_edit_key = f"exc_edit_{exc['id']}"
                if st.session_state.get(eg_edit_key):
                    nc1, nc2 = st.columns([3,1])
                    with nc1: new_exc_txt = st.text_input("คำยกเว้น", value=exc['exclude_text'], key=f"ext_{exc['id']}")
                    with nc2: new_grp = st.text_input("กลุ่ม", value=exc['group_name'], key=f"extg_{exc['id']}")
                    sc1, sc2 = st.columns([1,1])
                    with sc1:
                        if st.button("💾", key=f"ecsave_{exc['id']}"):
                            update_global_exclude(exc['id'], new_exc_txt, new_grp)
                            st.session_state[eg_edit_key] = False; st.rerun()
                    with sc2:
                        if st.button("↩️", key=f"eccancel_{exc['id']}"):
                            st.session_state[eg_edit_key] = False; st.rerun()
                else:
                    r1, r2, r3 = st.columns([5,1,1])
                    with r1: st.code(exc['exclude_text'], language=None)
                    with r2:
                        if st.button("✏️", key=f"ecedit_{exc['id']}"): st.session_state[eg_edit_key] = True; st.rerun()
                    with r3:
                        if st.button("🗑️", key=f"ecdel_{exc['id']}"): delete_global_exclude(exc['id']); st.rerun()

    with st.expander("➕ เพิ่มคำยกเว้นใหม่"):
        with st.form("add_exclude"):
            exc_txt = st.text_area("คำยกเว้น", placeholder='-site:example.com -"คำที่ไม่ต้องการ"')
            grp_choice = st.selectbox("กลุ่ม", options=exclude_group_names + ["[สร้างกลุ่มใหม่]"])
            new_grp_name = ""
            if grp_choice == "[สร้างกลุ่มใหม่]":
                new_grp_name = st.text_input("ชื่อกลุ่มใหม่")
            if st.form_submit_button("💾 บันทึก") and exc_txt:
                chosen = new_grp_name if grp_choice == "[สร้างกลุ่มใหม่]" else grp_choice
                insert_global_exclude(exc_txt, chosen or "ค่าเริ่มต้น"); st.success("เพิ่มสำเร็จ!"); st.rerun()

    st.markdown("---")

    # ── Province Groups ──
    st.subheader("🗺️ กลุ่มจังหวัด")
    for pg in province_groups:
        pg_edit_key = f"pg_edit_{pg['id']}"
        with st.expander(f"📍 {pg['group_name']}"):
            if st.session_state.get(pg_edit_key):
                ng = st.text_input("ชื่อกลุ่ม", value=pg['group_name'], key=f"pgname_{pg['id']}")
                np = st.text_area("รายชื่อจังหวัด (คั่นด้วย OR)", value=pg['provinces'], key=f"pgprov_{pg['id']}", height=80)
                pc1, pc2, pc3 = st.columns([1,1,1])
                with pc1:
                    if st.button("💾 บันทึก", key=f"pgsave_{pg['id']}"):
                        update_province_group(pg['id'], ng, np)
                        st.session_state[pg_edit_key] = False; st.rerun()
                with pc2:
                    if st.button("↩️ ยกเลิก", key=f"pgcancel_{pg['id']}"): st.session_state[pg_edit_key] = False; st.rerun()
                with pc3:
                    if st.button("🗑️ ลบ", key=f"pgdel_{pg['id']}"): delete_province_group(pg['id']); st.rerun()
            else:
                st.caption(pg['provinces'][:150] + ('...' if len(pg['provinces'])>150 else ''))
                if st.button("✏️ แก้ไข", key=f"pgedit_btn_{pg['id']}"): st.session_state[pg_edit_key] = True; st.rerun()

    with st.expander("➕ เพิ่มกลุ่มจังหวัดใหม่"):
        with st.form("add_pgroup"):
            pg_name = st.text_input("ชื่อกลุ่ม (เช่น ภาคเหนือ)")
            pg_provs = st.text_area("รายชื่อจังหวัด", placeholder="เชียงใหม่ OR เชียงราย OR ...", height=75)
            if st.form_submit_button("💾 บันทึก") and pg_name and pg_provs:
                insert_province_group(pg_name, pg_provs); st.success("เพิ่มสำเร็จ!"); st.rerun()

    st.markdown("---")

    # ── Search Summary ──
    st.subheader("📊 สรุปการค้นหา (ต่อรอบการรัน)")
    if not settings:
        st.info("ยังไม่มีชุดคำค้นหา")
    else:
        total_runs = sum(len(s.get('time_filters') or ['any']) for s in settings)
        st.markdown(f"""
| รายการ | จำนวน |
|---|---|
| จำนวนชุดคำค้นหา (Templates) | **{len(settings)}** |
| รวมรอบการค้นหาทั้งหมด (รวม Time Filters) | **{total_runs} ครั้ง/รอบ** |
| จำนวนกลุ่มจังหวัด | **{len(province_groups)}** |
        """)
        st.caption("⚠️ ถ้าแต่ละ Template มีหลาย Time Filter ระบบจะยิง API แยกกันตามจำนวนที่ติ๊กไว้")


def main():
    st.title("📋 Auction Discovery Dashboard")

    tab_inbox, tab_read, tab_settings = st.tabs(["📥 Inbox (ยังไม่อ่าน)", "✅ อ่านแล้ว", "⚙️ Settings"])

    with tab_inbox:
        auctions = get_auctions(unread_only=True)
        all_ = get_auctions(unread_only=False)
        read_count = sum(1 for a in all_ if a.get('is_read'))
        total = len(all_)
        st.markdown(f'<div class="summary-bar">📊 พบทั้งหมด <b>{total}</b> รายการ — อ่านแล้ว <b>{read_count}</b> / {total}</div>', unsafe_allow_html=True)
        if not auctions:
            st.success("ไม่มีรายการใหม่ในขณะนี้ 🎉")
        else:
            for idx, item in enumerate(auctions, 1):
                render_item(item, idx, is_read=False)

    with tab_read:
        all_ = get_auctions(unread_only=False)
        read = [a for a in all_ if a.get('is_read')]
        st.markdown(f'<div class="summary-bar">✅ รายการที่อ่านแล้วทั้งหมด <b>{len(read)}</b> รายการ</div>', unsafe_allow_html=True)
        if not read:
            st.info("ยังไม่มีรายการที่อ่านแล้ว")
        else:
            for idx, item in enumerate(read, 1):
                render_item(item, idx, is_read=True)

    with tab_settings:
        all_excludes = get_global_excludes()
        province_groups = get_province_groups()
        settings = get_search_settings()
        settings_tab(settings, all_excludes, province_groups)

if __name__ == "__main__":
    main()
