# -*- coding: utf-8 -*-
"""《档案学通讯》摘要语料：分词/停用词/TF-IDF/LDA 分析"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from corpus import CORPUS

# ---------- 停用词表（中文通用 + 语料特化） ----------
STOPWORDS = set("""的 了 在 是 我 你 他 她 它 我们 你们 他们 与 及 和 或 等 为 对 由 从 于 以 而 且 但 并 并按 并根据 其 该 此 这 那 之 之 内 外 中 上 下 前 后 时 能 可 会 将 已 也 都 只 就 还 又 再 更 最 很 甚 些 个 种 项 类 篇 章 条 款 点 面 者 员 所 被把 关于 对于 由于 因此 所以 然而 但是 但 如果 那么 以及 通过 利用 基于 面向 根据 围绕 作为 成为 其中 首先 其次 最后 发现 提出 分析 研究 探讨 探析 讨论 结果 表明 显示 目前 同时 以及 进行 开展 给出 文章 论文 本文 本研究 本刊 摘要 关键词 问题 方面 路径 策略 方式 方法 机制 体系 模式 框架 系统 内容 过程 状况 情况 领域 工作 事业 学科 理论 实践 时代 背景 特征 内涵 价值 意义 影响 作用 发展 建设 完善 优化 提升 提高 推动 促进 实现 形成 构建 提供 成为 亟待 有助 有助于 重要 核心 关键 主要 基础 依据 参考 借鉴 建议相应 目的 现状 现有 存在 面临 具有 带来 出现 日益 不断 进一步 更加 大幅 一系列 一定 某种 各类 各项 各种 多种 三个 两大 四个 八个 三大 两个 6个 9个 40个 81个 45所 28所 96名 9家 273份 30年 一类 一批 一样 不仅 而且 并 进而 从而 既 又 便 即 仅 仅是 仍 仍然 尚 未 不 无 没 没有 非 或许 也许 大约 左右 近 现代 当代 新型 新 变革 创新 转型 融合 应用 数据 档案 数字 智能化 数字化 资源 管理 治理 服务 利用 开放 开发 挖掘 归档 电子文件 电子档案 档案馆 部门 机构 政府 国家 社会文化 社会 中国 我国 相关 various 及其 二 者 龄""".split())
# 注：档案/数据等高频学科基础词在"全域词表版"停用策略中保留，以观察真实分布；另提供扩充版对照
EXTRA_STOP = set("档案 数据 数字 数字化 智能化 资源 管理 治理 服务 利用 开放 开发 归档 文件 研究".split())
DOMAIN_KEEP = set("档案 数据 数字 数字化 资源 管理 治理 服务 利用 开放 开发 归档 文件 档案馆")

def tokenize(text):
    words = jieba.lcut(text)
    return [w for w in words if len(w) > 1 and re.match(r"^[\u4e00-\u9fff]+$", w) and w not in STOPWORDS]

def tokenize_broad(text):
    """扩展停用词：额外剔除'档案/数据'等语料级超高频词，用于对照"""
    return [w for w in tokenize(text) if w not in EXTRA_STOP]

docs = CORPUS
texts = [d["title"] + "。" + d["abstract"] for d in docs]
toks = [tokenize(t) for t in texts]
toks_broad = [tokenize_broad(t) for t in texts]
print(f"语料数: {len(docs)}, 平均词数: {sum(len(t) for t in toks)/len(toks):.1f}")

results = {"n_docs": len(docs), "avg_tokens": round(sum(len(t) for t in toks)/len(toks),1)}

# ---------- TF-IDF 全域关键词 ----------
def tfidf_top(toks_list, n=25):
    corpus = [" ".join(t) for t in toks_list]
    vec = TfidfVectorizer(tokenizer=str.split, lowercase=False)
    X = vec.fit_transform(corpus)
    scores = X.sum(axis=0).A1
    inv = {v: k for k, v in vec.vocabulary_.items()}
    return sorted([(inv[i], round(float(scores[i]),2)) for i in range(len(inv))], key=lambda x:-x[1])[:n]

results["tfidf_global"] = tfidf_top(toks)
results["tfidf_broad"] = tfidf_top(toks_broad)

# ---------- LDA ----------
def run_lda(toks_list, k, topn=12):
    corpus = [" ".join(t) for t in toks_list]
    cv = CountVectorizer(tokenizer=str.split, lowercase=False, max_df=0.7, min_df=2)
    X = cv.fit_transform(corpus)
    lda = LatentDirichletAllocation(n_components=k, max_iter=800, learning_method="online",
                                    random_state=42, doc_topic_prior=0.1, topic_word_prior=0.01)
    doc_topic = lda.fit_transform(X)
    words = cv.get_feature_names_out()
    topics = []
    for ti, comp in enumerate(lda.components_):
        idx = comp.argsort()[::-1][:topn]
        tw = [(words[i], round(float(comp[i]/comp.sum()),4)) for i in idx]
        # 代表文档：该主题概率最高的2篇
        doc_rank = doc_topic[:, ti].argsort()[::-1][:3]
        reps = []
        for di in doc_rank:
            if doc_topic[di, ti] < 0.15: continue
            d = docs[di]
            # 回查例句：摘要中含高权重词的句子
            sent_hit = None
            for s in re.split(r"[。；]", d["abstract"]):
                s2 = s.strip()
                if s2 and any(w in s2 for w, _ in tw[:6]):
                    sent_hit = s2
                    break
            reps.append({"title": d["title"], "issue": d["issue"], "column": d["column"],
                         "prob": round(float(doc_topic[di, ti]),3), "example": sent_hit})
        topics.append({"id": ti, "top_words": tw, "examples": reps})
    # 稳定性：再跑一个随机种子，比较 top5 词重叠
    lda2 = LatentDirichletAllocation(n_components=k, max_iter=800, learning_method="online",
                                     random_state=7, doc_topic_prior=0.1, topic_word_prior=0.01)
    lda2.fit(X)
    w2 = cv.get_feature_names_out()
    w = w2
    top5a = [set(w[i] for i in c.argsort()[::-1][:5]) for c in lda.components_]
    top5b = [set(w2[i] for i in c.argsort()[::-1][:5]) for c in lda2.components_]
    overlaps = []
    for a in top5a:
        best = max(len(a & b)/len(a | b) for b in top5b)
        overlaps.append(round(best,2))
    return topics, round(sum(overlaps)/len(overlaps),3), overlaps

t4, ov4, ov4l = run_lda(toks, 4)
t6, ov6, ov6l = run_lda(toks, 6)
t8, ov8, ov8l = run_lda(toks, 8)
tb4, tbv4, _ = run_lda(toks_broad, 4)
results["lda_k4"] = {"topics": t4, "stability_jaccard": ov4, "per_topic": ov4l}
results["lda_k6"] = {"topics": t6, "stability_jaccard": ov6, "per_topic": ov6l}
results["lda_k8"] = {"topics": t8, "stability_jaccard": ov8}
results["lda_broad_k4"] = {"topics": tb4, "stability_jaccard": tbv4}

with open("results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("done -> results.json")
