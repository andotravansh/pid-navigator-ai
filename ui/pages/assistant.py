"""AI Assistant: optional Gemini Q&A grounded in the entered data."""

from __future__ import annotations

import streamlit as st

from modules.ai_interpreter import (
    DISCLAIMER,
    AIStatus,
    GeminiInterpreter,
    build_context,
    load_config,
)
from ui.components import callout, panel, section_heading
from ui.features import Status
from ui.state import load_page_images, log_activity


def render() -> None:
    """Draw the assistant section."""
    graph = st.session_state.graph
    config = load_config()
    interpreter = GeminiInterpreter(config)

    if interpreter.is_configured:
        callout(f"A Gemini API key was found. Model: {config.model}.", Status.EXPERIMENTAL,
                lead="Ready.")
    else:
        callout(
            "No GEMINI_API_KEY was found, so questions are switched off. The rest of the "
            "app works without it. See the README to enable it.",
            Status.PLANNED,
            lead="Not configured.",
        )
    st.caption(DISCLAIMER)

    context = build_context(graph)
    left, right = st.columns([1.5, 1], gap="large")
    with right:
        with panel("ai-context"):
            section_heading("Data sent to the model", "Exactly what the model can see.")
            st.code(context or "(nothing entered)", language="text")
    with left:
        with panel("ai-ask"):
            section_heading("Ask a question")
            images = load_page_images()
            send_image = st.checkbox(
                "Also send the current page image to Gemini",
                value=False,
                disabled=images.base is None,
                help="The image leaves your machine. Review the Gemini API terms for data handling.",
            )
            question = st.text_area(
                "Question", placeholder="What are the confirmed upstream items of E-101?",
                label_visibility="collapsed",
            )
            if st.button("Ask", type="primary", disabled=not interpreter.is_configured):
                with st.spinner("Waiting for Gemini"):
                    st.session_state.ai_response = interpreter.ask(
                        question, context, images.base if send_image else None
                    )
                log_activity("Asked the AI assistant")

        response = st.session_state.ai_response
        if response is None:
            return
        st.write("")
        if response.status is AIStatus.OK:
            st.markdown(response.text)
            st.caption(DISCLAIMER)
        elif response.status in (AIStatus.RATE_LIMITED, AIStatus.NO_CONTEXT, AIStatus.INVALID_INPUT):
            st.warning(response.message)
        elif response.status is AIStatus.NOT_CONFIGURED:
            st.info(response.message)
        else:
            st.error(response.message)
