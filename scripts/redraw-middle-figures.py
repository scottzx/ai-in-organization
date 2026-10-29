import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib import font_manager as fm
fp="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
fm.fontManager.addfont(fp); plt.rcParams["font.family"]=fm.FontProperties(fname=fp).get_name()
import os; OUT=os.path.join(os.path.dirname(__file__),"..","中册-行业解决方案","assets")+"/"
def box(ax,x,y,w,h,t,fc="white",fs=11,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02,rounding_size=0.08",fc=fc,ec="#333",lw=1))
    ax.text(x+w/2,y+h/2,t,ha="center",va="center",fontsize=fs,weight="bold" if bold else "normal",wrap=True)
def arrow(ax,x1,y1,x2,y2):
    ax.annotate("",(x2,y2),(x1,y1),arrowprops=dict(arrowstyle="-|>",color="#444",lw=1.2))
def layers(name,rows,side=None,note=None):
    # rows: top->bottom list of (label,[items])
    W=10+(2 if side else 0); n=len(rows)
    fig,ax=plt.subplots(figsize=(W*0.8,(n*1.5+0.6)*0.8)); ax.set_xlim(0,W); ax.set_ylim(0,n*1.5+0.4); ax.axis("off")
    for i,(lab,items) in enumerate(rows):
        y=(n-1-i)*1.5+0.3
        box(ax,0.1,y,1.9,1.1,lab,fc="#d9d9d9",bold=True)
        k=len(items); w=(7.7-0.15*(k-1))/k
        for j,it in enumerate(items): box(ax,2.2+j*(w+0.15),y+0.1,w,0.9,it,fs=10)
        if i<n-1: arrow(ax,6.05,y-0.05,6.05,y+0.05) 
    if side:
        lab,items=side; H=n*1.5-0.4
        box(ax,10.2,0.3,1.7,H,"",fc="#efefef")
        ax.text(11.05,0.3+H-0.3,lab,ha="center",va="top",fontsize=11,weight="bold")
        for j,it in enumerate(items): ax.text(11.05,0.3+H-0.9-j*0.55,it,ha="center",va="top",fontsize=10)
    fig.savefig(OUT+name,dpi=200,bbox_inches="tight",facecolor="white"); plt.close(fig)

layers("redraw-数字金融体系示意.png",[("服务",["渠道与客户服务","业务流程","运营支持"]),("能力",["数据治理","专业模型与业务规则","研发运维"]),("数字基础",["网络与存储","数据库","身份与接口"])],side=("治理",["安全","合规","风险管理","数据生命周期"]))
layers("redraw-智慧农业三层框架示意.png",[("应用层",["生产管理","产销与流通","溯源与社会化服务"]),("运算层",["数据","农业知识","算法与专业模型"]),("感知与执行层",["环境与遥感感知","农机与执行器","市场信息"])])
layers("redraw-数字乡村框架示意.png",[("建设领域",["智慧农业","乡村产业","乡村治理","公共服务"]),("两大基础",["数字基础设施","数据资源"])])
layers("redraw-智能云服务分层示意.png",[("AISaaS",["面向具体应用"]),("MaaS",["模型能力服务化"]),("AIPaaS",["数据","模型开发","部署流程"]),("AIIaaS",["算力","网络","存储"])])
layers("redraw-实时互动技术构成示意.png",[("共生技术",["终端呈现","课件与白板","交互操作"]),("专业组件",["音视频处理","信令","数据处理"]),("专有基础设施",["实时网络","边缘计算"])])
layers("redraw-数字政府一体化框架示意.png",[("驱动与牵引",["体制机制驱动","履职场景牵引"]),("业务应用",["一网通办","一网统管","一网协同"]),("两大支撑",["政务数据","政务平台"])],side=("两大保障",["运维运营","安全防护"]))
# 电信变革路径
fig,ax=plt.subplots(figsize=(9,3.6)); ax.set_xlim(0,11); ax.set_ylim(0,4.4); ax.axis("off")
for i,(lab,a,b) in enumerate([("基础设施","网络与资源","自感知、自调度"),("技术","平台与运维","数据与模型驱动"),("服务","客户服务","按需、主动服务")]):
    y=3.1-i*1.4; box(ax,0.1,y,1.8,0.9,lab,fc="#d9d9d9",bold=True); box(ax,2.4,y,3.0,0.9,a); box(ax,7.4,y,3.4,0.9,b); arrow(ax,5.5,y+0.45,7.3,y+0.45)
ax.text(3.9,4.25,"现状",ha="center",fontsize=11); ax.text(9.1,4.25,"智能化方向",ha="center",fontsize=11)
fig.savefig(OUT+"redraw-电信业智能化路径示意.png",dpi=200,bbox_inches="tight",facecolor="white"); plt.close(fig)
# 餐饮产业链
fig,ax=plt.subplots(figsize=(9,3.4)); ax.set_xlim(0,11); ax.set_ylim(0,4); ax.axis("off")
for j,(t,s) in enumerate([("数字供应","采购·运输·库存"),("数字加工","备餐·供餐"),("数字销售","堂食·外卖·其他渠道")]):
    box(ax,0.2+j*3.7,2.2,3.0,1.3,t+"\n"+s,fs=11)
    if j<2: arrow(ax,3.25+j*3.7,2.85,3.85+j*3.7,2.85)
box(ax,0.2,0.3,10.4,1.1,"数字管理：人员、财务、设备、食材",fc="#e6e6e6",fs=11)
for j in range(3): arrow(ax,1.7+j*3.7,1.45,1.7+j*3.7,2.15)
fig.savefig(OUT+"redraw-餐饮产业链示意.png",dpi=200,bbox_inches="tight",facecolor="white"); plt.close(fig)
# 餐饮矩阵
rows=[("数字供应","采购、运输、库存","供应商与食材记录"),("数字加工","备餐、供餐","工序与出品记录"),("数字管理","人、财、设备、食材","经营与资源记录"),("数字销售","堂食、外卖、其他渠道","订单与顾客记录")]
fig,ax=plt.subplots(figsize=(9,3.6)); ax.set_xlim(0,11); ax.set_ylim(0,5.2); ax.axis("off")
for j,h in enumerate(["环节","主要对象","数字化内容"]): box(ax,0.1+j*3.65,4.2,3.5,0.8,h,fc="#d9d9d9",bold=True)
for i,r in enumerate(rows):
    for j,c in enumerate(r): box(ax,0.1+j*3.65,3.2-i*1.0,3.5,0.8,c,fc="#f2f2f2" if j==0 else "white")
fig.savefig(OUT+"redraw-餐饮数字化环节矩阵示意.png",dpi=200,bbox_inches="tight",facecolor="white"); plt.close(fig)
