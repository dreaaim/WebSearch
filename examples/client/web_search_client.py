import sys
import io
import os
import json
import time
import threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import gradio as gr
from typing import List, Tuple

from web_search.core.orchestrator_v2 import SearchOrchestratorV2
from web_search.providers.searxng import SearXNGProvider
from web_search.classifier.source_classifier import SourceClassifier
from web_search.classifier.llm_classifier import LLMSourceClassifier
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge
from web_search.reranker.reranker import Reranker, RerankConfig
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.core.llm_client import create_llm_client
from web_search.core.embedding_client import create_embedding_client
from web_search.core.reranker_client import create_reranker_client
from web_search.config.settings import load_config

CSS = """
.search-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}
.stats-panel {
    display: flex;
    gap: 15px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 10px;
    margin-bottom: 20px;
    justify-content: center;
}
.stat-item {
    padding: 10px 20px;
    border-radius: 8px;
    text-align: center;
    min-width: 100px;
}
.stat-white {
    background: #d4edda;
    border: 1px solid #28a745;
    color: #155724;
}
.stat-gray {
    background: #fff3cd;
    border: 1px solid #ffc107;
    color: #856404;
}
.stat-black {
    background: #f8d7da;
    border: 1px solid #dc3545;
    color: #721c24;
}
.stat-label {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 5px;
}
.stat-value {
    font-size: 24px;
    font-weight: bold;
}
.result-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    border-left: 4px solid #6c757d;
}
.result-card-white {
    border-left-color: #28a745;
}
.result-card-gray {
    border-left-color: #ffc107;
}
.result-card-black {
    border-left-color: #dc3545;
}
.result-title {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 10px;
}
.result-title a {
    color: #1a0dab;
    text-decoration: none;
}
.result-title a:hover {
    text-decoration: underline;
}
.result-meta {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
    flex-wrap: wrap;
}
.classification-tag {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    color: white;
}
.tag-white {
    background-color: #28a745;
}
.tag-gray {
    background-color: #ffc107;
    color: #333;
}
.tag-black {
    background-color: #dc3545;
}
.result-date {
    font-size: 13px;
    color: #6c757d;
}
.result-score {
    font-size: 13px;
    color: #6c757d;
}
.result-snippet {
    font-size: 14px;
    line-height: 1.6;
    color: #495057;
    margin-bottom: 10px;
}
.result-url {
    font-size: 13px;
    color: #0066cc;
}
.result-url a {
    color: #0066cc;
    text-decoration: none;
    word-break: break-all;
}
.result-url a:hover {
    text-decoration: underline;
}
.summary-box {
    background: #e8f5e9;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    border-left: 4px solid #28a745;
}
.summary-title {
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 10px;
    color: #155724;
}
.summary-content {
    font-size: 14px;
    line-height: 1.8;
    color: #333;
    white-space: pre-wrap;
}
.consensus-box {
    background: #d4edda;
    border-radius: 10px;
    padding: 15px 20px;
    margin-bottom: 15px;
}
.disputed-box {
    background: #fff3cd;
    border-radius: 10px;
    padding: 15px 20px;
    margin-bottom: 15px;
}
.fact-title {
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 10px;
}
.fact-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.fact-list li {
    padding: 8px 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    font-size: 14px;
}
.fact-list li:last-child {
    border-bottom: none;
}
.fact-list li::before {
    margin-right: 8px;
    font-weight: bold;
}
.consensus-list li::before {
    content: "\u2705";
}
.disputed-list li::before {
    content: "\u26a0\ufe0f";
}
.debug-panel {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 20px;
    font-family: monospace;
    font-size: 12px;
    max-height: 500px;
    overflow-y: auto;
}
.error-box {
    background: #f8d7da;
    border: 1px solid #dc3545;
    border-radius: 10px;
    padding: 20px;
    color: #721c24;
    text-align: center;
}
.loading-text {
    text-align: center;
    padding: 40px;
    color: #6c757d;
    font-size: 16px;
}
.empty-results {
    text-align: center;
    padding: 40px;
    color: #6c757d;
    font-size: 16px;
    background: #f8f9fa;
    border-radius: 10px;
}
"""

orchestrator = None
init_error = None


def initialize_orchestrator():
    global orchestrator, init_error
    try:
        config = load_config("configs")

        llm_config = config.get("llm", {})
        embedding_config = config.get("embedding", {})
        reranker_config = config.get("reranker", {})

        llm_client = create_llm_client(llm_config)
        embedding_client = create_embedding_client(embedding_config)
        reranker_client = create_reranker_client(reranker_config.get("external_reranker", {}))

        provider = SearXNGProvider(base_url="http://localhost:8080")

        source_classifier = SourceClassifier(
            whitelist=config.get("whitelist", []),
            blacklist=config.get("blacklist", [])
        )

        reranker_weights = reranker_config.get("weights", {
            "relevance": 0.3,
            "trustworthiness": 0.2,
            "freshness": 0.1,
            "authority": 0.1,
            "external": 0.3
        })
        reranker_freshness = reranker_config.get("freshness", {})
        reranker_top_k = reranker_config.get("top_k", 10)

        orchestrator = SearchOrchestratorV2(
            provider=provider,
            source_classifier=source_classifier,
            llm_classifier=LLMSourceClassifier(llm_client=llm_client),
            query_rewriter=QueryRewriter(llm_client=llm_client),
            embedding_engine=EmbeddingSimilarityEngine(embedding_client=embedding_client),
            collision_judge=LLMCollisionJudge(llm_client=llm_client),
            reranker=Reranker(
                config=RerankConfig(
                    weights=reranker_weights,
                    external_rerank_weight=reranker_weights.get("external", 0.3),
                    top_k=reranker_top_k
                ),
                freshness_config=reranker_freshness,
                reranker_client=reranker_client
            ),
            use_v2_features=True
        )
        init_error = None
        return True
    except Exception as e:
        init_error = str(e)
        orchestrator = None
        return False


def get_classification_label(result) -> Tuple[str, str]:
    if hasattr(result, 'classification'):
        class_value = result.classification.value if hasattr(result.classification, 'value') else str(result.classification)
        labels = {
            "white": ("高可信", "tag-white", "result-card-white"),
            "gray": ("中可信", "tag-gray", "result-card-gray"),
            "black": ("低可信", "tag-black", "result-card-black"),
        }
        return labels.get(class_value, ("未知", "tag-gray", "result-card-gray"))
    elif hasattr(result, 'source_info') and result.source_info:
        return ("中可信", "tag-gray", "result-card-gray")
    return ("未知", "tag-gray", "result-card-gray")


def get_score(result) -> float:
    return getattr(result, 'final_score', None) or \
           getattr(result, 'relevance_score', None) or \
           getattr(result, 'external_rerank_score', None) or 0.0


def format_result_card(result, index: int) -> str:
    label, tag_class, card_class = get_classification_label(result)
    score = get_score(result)

    title_html = f'<div class="result-title"><a href="{result.url}" target="_blank">{result.title}</a></div>'

    meta_parts = [f'<span class="classification-tag {tag_class}">{label}</span>']

    if hasattr(result, 'published_date') and result.published_date:
        meta_parts.append(f'<span class="result-date">\U0001f4c5 {result.published_date}</span>')

    meta_parts.append(f'<span class="result-score">\U0001f4ca Score: {score:.4f}</span>')

    meta_html = '<div class="result-meta">' + ''.join(meta_parts) + '</div>'

    snippet = result.snippet[:300] + "..." if len(result.snippet) > 300 else result.snippet
    snippet_html = f'<div class="result-snippet">{snippet}</div>'

    url_html = f'<div class="result-url">\U0001f517 <a href="{result.url}" target="_blank">{result.url}</a></div>'

    return f'<div class="result-card {card_class}">{title_html}{meta_html}{snippet_html}{url_html}</div>'


def perform_search(query: str, show_debug: bool) -> Tuple[str, str, str, str, str, str, str]:
    global orchestrator, init_error

    if orchestrator is None:
        error_html = f'''
        <div class="error-box">
            <h2>\u274c 搜索引擎初始化失败</h2>
            <p>错误信息: {init_error or "未知错误"}</p>
            <p>请检查配置文件和依赖是否正确安装。</p>
        </div>
        '''
        return error_html, "", "", "", "", "", ""

    if not query or not query.strip():
        return '<div class="empty-results">请输入搜索关键词</div>', "", "", "", "", "", ""

    try:
        result = orchestrator.search_with_trust(
            query,
            debug=show_debug,
            debug_level="verbose" if show_debug else "basic",
            debug_output="stdout"
        )

        white_count = result.metadata.get("white_count", 0)
        gray_count = result.metadata.get("gray_count", 0)
        black_count = result.metadata.get("black_count", 0)

        stats_html = f'''
        <div class="stats-panel">
            <div class="stat-item stat-white">
                <div class="stat-label">\u2705 高可信</div>
                <div class="stat-value">{white_count}</div>
            </div>
            <div class="stat-item stat-gray">
                <div class="stat-label">\u26a0\ufe0f 中可信</div>
                <div class="stat-value">{gray_count}</div>
            </div>
            <div class="stat-item stat-black">
                <div class="stat-label">\u274c 低可信</div>
                <div class="stat-value">{black_count}</div>
            </div>
            <div class="stat-item" style="background: #e9ecef; padding: 10px 20px; border-radius: 8px;">
                <div class="stat-label">\u23f1\ufe0f 耗时</div>
                <div class="stat-value">{result.total_duration_ms / 1000:.1f}s</div>
            </div>
        </div>
        '''

        results_html = ""
        if result.response.results:
            for i, r in enumerate(result.response.results, 1):
                results_html += format_result_card(r, i)
        else:
            results_html = '<div class="empty-results">\U0001f50d 未找到相关结果</div>'

        summary_html = ""
        if result.summary:
            summary_html = f'''
            <div class="summary-box">
                <div class="summary-title">\U0001f4dd AI 摘要</div>
                <div class="summary-content">{result.summary}</div>
            </div>
            '''

        consensus_html = ""
        if result.consensus_facts:
            facts_list = "".join([f"<li>{fact}</li>" for fact in result.consensus_facts])
            consensus_html = f'''
            <div class="consensus-box">
                <div class="fact-title" style="color: #155724;">\u2705 共识事实 ({len(result.consensus_facts)})</div>
                <ul class="fact-list consensus-list">{facts_list}</ul>
            </div>
            '''

        disputed_html = ""
        if result.disputed_facts:
            facts_list = "".join([f"<li>{fact}</li>" for fact in result.disputed_facts])
            disputed_html = f'''
            <div class="disputed-box">
                <div class="fact-title" style="color: #856404;">\u26a0\ufe0f 争议事实 ({len(result.disputed_facts)})</div>
                <ul class="fact-list disputed-list">{facts_list}</ul>
            </div>
            '''

        debug_html = ""
        if show_debug and result.debug_info:
            debug_json = json.dumps(result.debug_info, indent=2, ensure_ascii=False, default=str)
            debug_html = f'<div class="debug-panel"><pre>{debug_json}</pre></div>'

        return stats_html, results_html, summary_html, consensus_html, disputed_html, debug_html, ""

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_html = f'''
        <div class="error-box">
            <h2>\u274c 搜索过程中发生错误</h2>
            <p>错误信息: {str(e)}</p>
            <details>
                <summary>查看详细错误</summary>
                <pre style="text-align: left; font-size: 12px; margin-top: 10px;">{error_details}</pre>
            </details>
        </div>
        '''
        return error_html, "", "", "", "", "", ""


def create_demo():
    header_md = """
    # \U0001f50d 可信搜索引擎

    基于 AI 的可信搜索结果聚合与摘要生成系统
    """

    with gr.Blocks(css=CSS, title="可信搜索引擎") as demo:
        gr.Markdown(header_md)

        with gr.Row():
            with gr.Column(scale=4):
                search_input = gr.Textbox(
                    placeholder="请输入搜索关键词...",
                    label="搜索",
                    lines=1,
                    show_label=False,
                )
            with gr.Column(scale=1, min_width=120):
                search_btn = gr.Button("\U0001f50d 搜索", variant="primary", size="lg")

        with gr.Row():
            show_debug = gr.Checkbox(label="显示调试信息", value=False)

        stats_output = gr.HTML()

        summary_output = gr.HTML()

        with gr.Row():
            with gr.Column():
                consensus_output = gr.HTML()
            with gr.Column():
                disputed_output = gr.HTML()

        results_output = gr.HTML()

        with gr.Accordion("\U0001f41b 调试信息", open=False):
            debug_output = gr.HTML()

        error_output = gr.HTML(visible=False)

        search_inputs = [search_input, show_debug]
        search_outputs = [stats_output, results_output, summary_output, consensus_output, disputed_output, debug_output, error_output]

        search_btn.click(
            fn=perform_search,
            inputs=search_inputs,
            outputs=search_outputs,
        )

        search_input.submit(
            fn=perform_search,
            inputs=search_inputs,
            outputs=search_outputs,
        )

        gr.Markdown("---")
        gr.Markdown("<center style='color: #6c757d; font-size: 12px;'>Powered by WebSearch \U0001f680</center>")

    return demo


def main():
    print("\U0001f680 正在初始化搜索引擎...")
    success = initialize_orchestrator()
    if success:
        print("\u2705 搜索引擎初始化成功!")
    else:
        print(f"\u274c 搜索引擎初始化失败: {init_error}")
        print("UI 仍将启动，但搜索功能将显示错误信息。")

    demo = create_demo()
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
