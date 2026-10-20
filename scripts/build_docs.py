"""Generate the architecture PDF, offline HTML, Markdown and vector diagrams.

Optional documentation dependency: reportlab. Run from any directory.
"""
from pathlib import Path
import html
import json
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF, renderSVG

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs'
OUT.mkdir(exist_ok=True)
font_path = Path('/usr/share/fonts/truetype/dejavu')
if font_path.exists():
    pdfmetrics.registerFont(TTFont('Body', str(font_path/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('Body-Bold', str(font_path/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='Body-Bold', italic='Body', boldItalic='Body-Bold')
else:
    # Portable fallback: all document text is ASCII.
    pdfmetrics.registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold', italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
FONT = 'Body' if font_path.exists() else 'Helvetica'
BOLD = FONT+'-Bold'
INK = colors.black
MUTED = colors.black
PALE = colors.white
LINE = colors.black
TEAL = colors.black
AMBER = colors.black


def box(d,x,y,w,h,title,lines=(),planned=False):
    d.add(Rect(x,y,w,h,rx=6,fillColor=colors.white,
               strokeColor=AMBER if planned else TEAL,strokeWidth=1,strokeDashArray=[4,3] if planned else None))
    d.add(String(x+w/2,y+h-17,title,fontName='Helvetica-Bold',fontSize=10,fillColor=INK,textAnchor='middle'))
    for i,line in enumerate(lines):
        d.add(String(x+w/2,y+h-33-i*12,line,fontName='Helvetica',fontSize=8.4,fillColor=MUTED,textAnchor='middle'))


def arrow(d,points,label=None,planned=False,lx=None,ly=None):
    color=AMBER if planned else TEAL
    for a,b in zip(points,points[1:]):
        d.add(Line(*a,*b,strokeColor=color,strokeWidth=1.15,strokeDashArray=[4,3] if planned else None))
    x,y=points[-1]; px,py=points[-2]
    import math
    angle=math.atan2(y-py,x-px);size=4.5
    d.add(Polygon([x,y,x-size*math.cos(angle-.5),y-size*math.sin(angle-.5),x-size*math.cos(angle+.5),y-size*math.sin(angle+.5)],fillColor=color,strokeColor=color))
    if label:
        d.add(String(lx if lx is not None else (x+px)/2,ly if ly is not None else (y+py)/2+4,label,fontName='Helvetica',fontSize=7.5,fillColor=MUTED,textAnchor='middle'))


def architecture():
    d=Drawing(510,310)
    box(d,0,239,145,60,'React interface',['Catalogue + setup now','Chat + comparison on Day 2'])
    box(d,182,239,145,60,'FastAPI REST API',['Validation + error handling','Five working routes; one 501'])
    box(d,365,239,145,60,'Agent controller',['State, questions, ranking','Grounded response builder'],True)
    arrow(d,[(145,271),(182,271)],'HTTP',lx=163,ly=280)
    arrow(d,[(327,271),(365,271)],planned=True)
    box(d,0,123,145,64,'Conversation store',['Current requirements','Ordered message history'])
    box(d,182,123,145,64,'Controlled search',['Category + budget now','More hard filters on Day 2'])
    box(d,365,123,145,64,'Gemini API adapter',['gemini-3.8-flash','Free tier; planned for Day 2'],True)
    arrow(d,[(220,239),(220,213),(73,213),(73,187)])
    arrow(d,[(255,239),(255,187)])
    arrow(d,[(425,239),(425,187)],'Extract',planned=True,lx=400,ly=209)
    arrow(d,[(451,187),(451,239)],'Return',planned=True,lx=474,ly=209)
    arrow(d,[(365,253),(344,253),(344,202),(302,202),(302,187)],planned=True)
    box(d,80,22,275,62,'PostgreSQL database',['products  |  conversations  |  messages','SQLite preview supported; JSON replaces JSONB'])
    arrow(d,[(73,123),(73,103),(160,103),(160,84)])
    arrow(d,[(255,123),(255,84)])
    d.add(String(365,77,'Solid: Day 1 working path',fontName='Helvetica',fontSize=8,fillColor=TEAL))
    d.add(String(365,63,'Dashed: planned agent path',fontName='Helvetica',fontSize=8,fillColor=AMBER))
    d.add(String(365,46,'Controller accesses stored',fontName='Helvetica',fontSize=8,fillColor=MUTED))
    d.add(String(365,34,'state through the backend.',fontName='Helvetica',fontSize=8,fillColor=MUTED))
    return d


def flow():
    d=Drawing(510,380)
    box(d,130,330,250,45,'1. Receive message',['Validate input and load saved requirements'],True)
    box(d,130,270,250,45,'2. Interpret and validate',['LLM proposes changes; application merges them'],True)
    arrow(d,[(255,330),(255,315)],planned=True)
    box(d,130,210,250,45,'3. Decide the next action',['Important missing detail or unresolved conflict?'],True)
    arrow(d,[(255,270),(255,255)],planned=True)
    box(d,0,140,150,48,'Ask a question',['Focused clarification only'],True)
    box(d,185,140,195,48,'Search and filter',['Enforce all mandatory constraints'],True)
    arrow(d,[(130,234),(75,234),(75,188)],'Yes',True,lx=98,ly=242)
    arrow(d,[(284,210),(284,188)],'No',True,lx=299,ly=198)
    box(d,185,70,150,49,'Rank + explain',['Up to two eligible records'],True)
    box(d,360,70,150,49,'Explain no match',['Ask before relaxing a rule'],True)
    arrow(d,[(255,140),(255,119)],'Matches',True,lx=285,ly=127)
    arrow(d,[(380,165),(435,165),(435,119)],'None',True,lx=460,ly=138)
    box(d,130,0,250,45,'Save turn and valid state',['Continue with the next customer message'],True)
    arrow(d,[(75,140),(75,23),(130,23)],planned=True)
    arrow(d,[(260,70),(260,45)],planned=True)
    arrow(d,[(435,70),(435,23),(380,23)],planned=True)
    return d


def entities():
    d=Drawing(510,173)
    box(d,0,23,155,139,'products',['id [PK]','name, category, currency','price_paise [integer]','specifications [JSONB]','intended_uses, features'])
    box(d,182,23,155,139,'conversations',['id [UUID PK]','requirements [JSONB]','status','created_at, updated_at'])
    box(d,365,23,145,139,'messages',['id [UUID PK]','conversation_id [FK]','role, content','created_at'])
    arrow(d,[(337,95),(365,95)],'1 : N',lx=351,ly=106)
    d.add(String(255,7,'Products are retrieved by ID. Recommendation persistence is planned for Day 2.',fontName='Helvetica',fontSize=8,fillColor=MUTED,textAnchor='middle'))
    return d


class Document:
    def __init__(self):
        self.c=canvas.Canvas(str(OUT/'Day1_Architecture.pdf'),pagesize=(595.28,841.89))
        self.c.setTitle('Electronics Sales Assistant - Day 1 Architecture')
        self.c.setAuthor('AI Engineer Assessment Project')
        self.parts=[];self.md=[];self.n=0
        self.style=ParagraphStyle('body',fontName=FONT,fontSize=9.4,leading=14,textColor=INK)
        self.cellstyle=ParagraphStyle('cell',parent=self.style,fontSize=8.4,leading=12)

    def page(self,kicker,title,subtitle):
        if self.n:
            self.finish_page()
        self.n+=1
        self.c.setFillColor(INK);self.c.setFont(BOLD,20);self.c.drawString(42,786,title)
        self.c.setFont(FONT,9);self.c.drawString(42,764,subtitle)
        self.y=737
        self.parts.append(f'<section class="page"><h1>{html.escape(title)}</h1><p class="subtitle">{html.escape(subtitle)}</p>')
        self.md.append(f'# {title}\n\n{subtitle}\n')

    def p(self,text,space=10):
        p=Paragraph(text,self.style);w,h=p.wrap(510,800)
        self.y-=h;p.drawOn(self.c,42,self.y);self.y-=space
        self.parts.append('<p>'+text+'</p>')
        self.md.append(text.replace('<b>','**').replace('</b>','**')+'\n')
        assert self.y>48,(self.n,self.y,text)

    def heading(self,text):
        self.y-=8;self.c.setFont(BOLD,12);self.c.setFillColor(INK);self.c.drawString(42,self.y,text);self.y-=21
        self.parts.append('<h2>'+html.escape(text)+'</h2>');self.md.append('## '+text+'\n')

    def table(self,headers,rows,widths):
        cells=[[Paragraph('<b>'+html.escape(str(v))+'</b>',self.cellstyle) for v in headers]]
        cells += [[Paragraph(html.escape(str(v)),self.cellstyle) for v in row] for row in rows]
        table=Table(cells,colWidths=widths,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.6,LINE),('LINEBELOW',(0,1),(-1,-1),.4,LINE)]))
        _,h=table.wrap(510,800);self.y-=h;table.drawOn(self.c,42,self.y);self.y-=15
        self.parts.append('<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>')
        self.md += ['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows]+['']
        assert self.y>48,(self.n,self.y)

    def diagram(self,d,name):
        renderSVG.drawToFile(d,str(OUT/name))
        self.y-=d.height;renderPDF.draw(d,self.c,42,self.y);self.y-=14
        svg=(OUT/name).read_text();svg=svg[svg.index('<svg'):]
        self.parts.append('<div class="diagram">'+svg+'</div>')
        self.md.append(f'![{name.replace(".svg","").replace("-"," ")}]({name})\n')
        assert self.y>48,(self.n,self.y)

    def finish_page(self):
        self.c.showPage()
        self.parts.append('</section>')

    def finish(self):
        self.finish_page();self.c.save()
        (OUT/'architecture.md').write_text('\n'.join(self.md),encoding='utf-8')
        css='body{margin:0;background:white;color:black;font:14px/1.6 Georgia,serif}.page{max-width:820px;padding:48px;background:white;margin:0 auto;box-sizing:border-box}h1{font-size:26px;line-height:1.2}h2{font-size:18px;margin-top:25px}.subtitle{font-size:13px}.diagram svg{width:100%;height:auto}table{width:100%;border-collapse:collapse;font-size:12px;margin:18px 0}th,td{text-align:left;vertical-align:top;padding:11px;border-bottom:1px solid black}th{background:white}@media print{.page{margin:0;page-break-after:always;max-width:none;padding:28px}h1{font-size:23px}p,td,th{font-size:10px}}'
        (OUT/'architecture.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Day 1 Architecture</title><style>'+css+'</style></head><body>'+''.join(self.parts)+'</body></html>',encoding='utf-8')


def main():
    doc=Document()
    doc.page('01 / System architecture','Electronics Sales Assistant','Proposed System Architecture and Implementation Plan')
    doc.p('Help a customer turn an everyday need into <b>up to two suitable electronics choices</b>. The final agent will clarify important gaps, remember revisions and explain trade-offs using retrieved catalogue records.')
    doc.diagram(architecture(),'system-architecture.svg')
    doc.heading('Component Responsibilities')
    doc.p('<b>Language model:</b> propose structured requirement changes. <b>Application:</b> validate and merge state, decide whether to clarify, enforce hard constraints, rank eligible records and assemble factual responses.')
    doc.p('<b>Stack:</b> FastAPI + React meet the FARM requirement. PostgreSQL stores products and conversations; SQLite is a tested preview. <b>Planned AI:</b> Google Gemini Developer API, Gemini 3.8 Flash, free tier. Provider integration and account quota verification are Day 2 work; see External AI Service.')
    doc.p('<b>Communication:</b> React exchanges REST requests and JSON responses with FastAPI over HTTP in local development. The backend uses parameterized SQLAlchemy queries over a PostgreSQL connection. The planned Gemini adapter exchanges structured JSON over HTTPS. Only the backend accesses the database and external API.')
    doc.p('<b>Day 1 boundary:</b> catalogue and conversation setup work. AI message processing is explicitly unavailable (HTTP 501). No invented or simulated AI answer is shown.')
    doc.page('02 / Agent behaviour','Agent Decision Flow','Planned Day 2 flow; the controller is not implemented in this delivery')
    doc.diagram(flow(),'agent-flow.svg')
    doc.p('Both recommendation and no-match branches will save their response and valid state before the next turn. Failures must not corrupt previously valid requirements. All agent branches above are planned, not running today.')
    doc.heading('Conversation State and Clarification Policy')
    doc.p('"Maximum INR 70,000; programming; lighter preferred" creates a hard budget and a soft portability preference. "Actually, INR 60,000" replaces only the budget. "Weight does not matter" explicitly removes the weight preference.')
    doc.p('<b>Question policy:</b> ask only when an unknown or contradiction can materially change a useful recommendation. A complete first request can search immediately. An explicit "no budget limit" is an answer, not a missing value.')
    doc.p('<b>No match:</b> preserve all hard constraints, explain the mismatch and ask which condition the customer is willing to adjust. Do not silently relax a budget or invent a product.')
    doc.page('03 / Data design','Database Design','36 fictional catalogue records: 24 laptops and 12 headphones; INR only')
    doc.diagram(entities(),'data-model.svg')
    doc.table(['Record','Structured content'],[
        ['Laptop specifications','RAM, storage, CPU, GPU, VRAM where applicable, weight and operating system.'],
        ['Headphone specifications','Connection type, microphone, noise cancellation, weight, battery hours and battery applicability.'],
        ['Requirement state','Category, intended uses, mandatory constraints, preferences, explicit no-preference answers and unresolved questions.'],
        ['Sample-data coverage','Budget boundaries, several/one/no eligible matches, portability trade-offs and unknown optional specifications.']
    ],[145,365])
    doc.heading('Data rules')
    doc.p('<b>Money:</b> integer paise, so INR 70,000 is stored as 7,000,000. <b>Unknowns:</b> null means not specified; battery applicability distinguishes unknown wireless battery life from a wired product with no battery.')
    doc.p('<b>Persistence:</b> conversations own their messages through a foreign key. Retrieval orders history by timestamp and ID. JSONB is used on PostgreSQL; JSON is used in the SQLite preview. Day 2 updates must replace or explicitly track changed JSON state.')
    doc.p('<b>Seed safety:</b> validate records before insertion; skip existing IDs and preserve edits. Synthetic intended-use tags are not measured performance claims. No recommendation may cite an attribute absent from the retrieved record.')
    doc.page('04 / API and controls','Backend API and System Controls','All six required endpoint paths are documented; five are functional today')
    doc.table(['Endpoint','Day 1 behaviour'],[
        ['GET /api/v1/products','200: category and inclusive max-price filters; stable ordering; pagination and total count.'],
        ['GET /api/v1/products/{product_id}','200 stored product; 404 if absent.'],
        ['POST /api/v1/conversations','201: persist a UUID conversation with empty requirement state.'],
        ['GET /api/v1/conversations/{conversation_id}','200: current state and ordered history; 404 if absent.'],
        ['POST /api/v1/conversations/{conversation_id}/messages','501 for a valid known conversation: agent_not_implemented. No message is saved. Invalid input: 422. Unknown conversation: 404.'],
        ['GET /api/v1/health','200 when the database connects; 503 otherwise. Reports agent not implemented. Connectivity only, not schema readiness.']
    ],[250,260])
    doc.heading('Validation and Reliability Controls')
    doc.p('<b>Implemented:</b> validated API inputs, safe parameterized queries, typed sample specifications, database constraints and sanitized errors. Catalogue sorting is price then ID; it is not recommendation ranking.')
    doc.p('<b>Planned:</b> allowlisted agent tools; schema-validated model output; bounded timeouts/recovery; hard-constraint filtering before scoring; grounded explanations; atomic state/message processing and per-conversation concurrency control.')
    doc.p('<b>Local use:</b> no authentication or public deployment is included. Model credentials will remain in the backend. React never receives secrets. Product data comes from the database, not model memory.')
    doc.p('<b>Documentation:</b> live Swagger UI at /docs, OpenAPI at /openapi.json, plus a saved schema snapshot in docs/openapi.json. Configuration templates and exact setup commands are included in the README.')
    doc.page('05 / Delivery and review','Implementation Plan and Day 1 Coverage','A realistic route from today\'s architecture to the final demonstration')
    doc.table(['Milestone','Deliverable and exit condition'],[
        ['Day 1 - 19 October\n9:00 PM check-in','Submit this architecture. Foundation: catalogue, persistence, API contracts, minimal UI, setup guide and initial tests.'],
        ['Day 2 - 20 October\n9:00 PM check-in','Submit progress README. Implement real extraction, requirement memory, clarification, eligibility/ranking, grounded responses and behavioural tests.'],
        ['Day 3 - 21 October\nGoogle Meet; time to follow','Finalize code, schema/sample data, tests and configuration. Verify clean setup, rehearse, explain trade-offs and be ready to debug live.']
    ],[155,355])
    doc.heading('Verification and current limits')
    verification=json.loads((OUT/'verification.json').read_text()) if (OUT/'verification.json').exists() else {}
    doc.p(verification.get('summary','Backend: 40 automated tests passed using isolated SQLite databases. Frontend and browser checks are pending final verification. PostgreSQL/Docker execution is not available in this workspace.'))
    doc.p('<b>Not yet verified or implemented:</b> PostgreSQL integration execution, real-model conversations, recommendation quality, concurrent turn handling and public-hosting controls. These are explicit follow-up work, not completed claims.')
    doc.heading('Day 1 Submission Coverage')
    doc.table(['Required element','Location and content'],[
        ['Main components','System architecture diagram: React, FastAPI, controller, search, conversation store, database and Gemini adapter.'],
        ['Agent flow','Agent Decision Flow: interpret, validate, clarify or search, filter, rank, explain and save state.'],
        ['Database','Database Design: product, conversation and message entities, relationships and structured fields.'],
        ['API/backend','Backend API and System Controls: six required endpoint paths, responsibilities and status handling.'],
        ['Component communication','System diagram arrows and communication explanation: REST/JSON, database queries, HTTPS model requests and persisted state.'],
        ['Short explanation of plan','Component responsibilities, data rules, implementation milestones and external API integration plan.']
    ],[145,365])
    doc.page('06 / External AI decision','External AI Service','Selected provider, model, free-tier constraints and planned integration')
    doc.table(['Decision','Planned implementation'],[
        ['External service','Google Gemini Developer API; obtain a backend API key through Google AI Studio.'],
        ['Selected model','Gemini 3.8 Flash, model ID gemini-3.8-flash. Keep the model configurable and confirm account availability before integration.'],
        ['Cost boundary','Use a Free-tier project. Standard input/output tokens are currently listed as free. Do not enable paid billing or automatically fall back to a paid service.'],
        ['Model task','Interpret messages and return structured requirement changes. Validate JSON with Pydantic and check business meaning before changing state.'],
        ['Local application task','Store requirements, enforce constraints, query PostgreSQL, rank eligible records and build product comparisons from retrieved fields.'],
        ['Training and hardware','No local training, fine-tuning, GPU or model downloads. The synthetic catalogue is application data, not a training dataset.']
    ],[132,378])
    doc.heading('Quota-aware integration plan')
    doc.p('Target one extraction call per customer turn and build factual comparison text locally. Use bounded input/output sizes, a timeout and at most one bounded retry for recoverable errors. Handle 429/quota exhaustion visibly; never invent an answer or silently switch to paid usage.')
    doc.p('Free quotas vary by model, project and account and are not guaranteed. Check active RPM/TPM/RPD limits in AI Studio and perform a small real-key smoke test before the demonstration. No API key or account quota has been tested in this Day 1 delivery.')
    doc.p('<b>Credentials and data:</b> keep GEMINI_API_KEY only in the backend environment; never in React or Git. The free tier may use submitted content to improve Google products. Send synthetic demo requests and necessary state only, never database credentials or personal customer data.')
    doc.p('<b>Status:</b> this is a documented provider choice, not a completed integration. Day 1 still returns HTTP 501 for messages. Day 2 implements and verifies the adapter. No Google Search grounding, external shopping data or paid add-on tools are needed.')
    doc.finish()
    print('Generated six-page PDF, offline HTML, Markdown and three SVG diagrams.')


if __name__=='__main__':
    main()
