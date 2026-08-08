import asyncio
import json
from pathlib import Path
from uuid import uuid4

from phoenix.client import Client
from phoenix.client.types.spans import SpanQuery
from phoenix.evals import LLM, async_evaluate_dataframe, bind_evaluator
from phoenix.evals.metrics import ToolInvocationEvaluator, ToolSelectionEvaluator
from phoenix.evals.utils import to_annotation_dataframe

from agent.core.config import settings
from agent.core.observability import agent_turn_span, phoenix_observability
from agent.services.agent_runner import AgentRunner
from agent.services.mcp_client import MCPClient
from agent.services.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from evals.fake_mcp import FakeSallaStore

DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "fake_store_data.json"
EVALUATION_CONCURRENCY = 5


async def load_tool_schemas() -> list[dict]:
    client = MCPClient()
    async with client.connect() as connection:
        return await client.get_openai_tools(connection)


agent_questions = [
    "What is my store's name, domain, and operating currency?",
    # "Which products are currently out of stock? Include each product's ID, SKU, and price.",
    # "Show me the full product details for the Arabic coffee with product ID 101.",
    # "Create a food product named 'Saudi Date Cookies' priced at 32 SAR, with SKU DATE-COOKIE-01, an initial quantity of 40, and status set to sale.",
    # "We received new inventory for product 102. Update its quantity to 35 and make it available for sale.",
    # "Which orders are currently under review? Include the order ID, customer name, and total.",
    # "Give me the full details for order 5002 so I can answer the customer's support request.",
    # "Mark order 5001 as completed and add the note 'Payment verified and order fulfilled'.",
    # "Find the customer with email sara@example.test, then show me her complete customer record.",
    # "Create a customer named Laila Hassan with mobile 500000003, country code +966, and email laila@example.test. Then place a pickup, cash-on-delivery order for her containing one unit of product 101.",
    # "ما اسم متجري وما هو رابط النطاق والعملة المستخدمة فيه؟",
    # "اعرض لي جميع المنتجات المتاحة للبيع مع رقم المنتج ورمز SKU والسعر والكمية المتوفرة.",
    # "أريد معرفة التفاصيل الكاملة لمنتج الدفتر الإنجليزي الذي يحمل رقم 102.",
    # "أنشئ منتجًا جديدًا من نوع منتج باسم 'كوب قهوة حراري' بسعر 65 ريالًا، ورمز SKU هو MUG-THERMAL-01، وكمية أولية 25، واجعله متاحًا للبيع.",
    # "حدّث سعر منتج القهوة العربية رقم 101 إلى 49 ريالًا، واضبط الكمية المتوفرة على 30 قطعة.",
    # "اعرض الطلبات المكتملة مع رقم كل طلب واسم العميل والإجمالي والعملة.",
    # "اعرض لي التفاصيل الكاملة للطلب رقم 5001 لمراجعتها قبل التواصل مع العميل.",
    # "أعد حالة الطلب رقم 5002 إلى قيد المراجعة، وأضف ملاحظة 'بانتظار تأكيد عنوان الشحن'.",
    # "ابحث عن العميل الذي يحمل رقم الجوال 500000001، ثم اعرض سجله الكامل.",
    # "أنشئ عميلًا جديدًا باسم Omar Khaled ورقم جوال 500000004 مع رمز الدولة +966 والبريد omar@example.test، ثم أنشئ له طلب شحن مدفوعًا بمدى يحتوي على قطعتين من المنتج ذي الرمز NOTE-A5.",
]


def extract_tool_selection(value) -> str | None:
    try:
        response = json.loads(value) if isinstance(value, str) else value
        choices = response.get("choices", [])
    except (AttributeError, json.JSONDecodeError, TypeError):
        return None

    tool_calls = []
    for choice in choices:
        message = choice.get("message") or {}
        tool_calls.extend(message.get("tool_calls") or [])

    if not tool_calls:
        return None
    return json.dumps(tool_calls, ensure_ascii=False)


def load_llm_spans(conversation_ids: set[str]):
    phx_client = Client(base_url=settings.phoenix_base_url)
    query = (
        SpanQuery()
        .where(
            "span_kind == 'LLM' and "
            "llm.tools is not None and "
            "output.value is not None"
        )
        .select(
            "input.value",
            "llm.tools",
            "output.value",
            "llm.model_name",
            "session.id",
        )
        .rename(
            **{
                "input.value": "input",
                "llm.tools": "available_tools",
                "output.value": "output",
                "llm.model_name": "model",
                "session.id": "conversation_id",
            }
        )
    )
    llm_spans = phx_client.spans.get_spans_dataframe(
        query=query,
        project_identifier=settings.phoenix_project_name,
        timeout=None,
    )
    if llm_spans.empty:
        return llm_spans

    llm_spans = llm_spans[
        llm_spans["conversation_id"].isin(conversation_ids)
    ].copy()
    llm_spans["tool_selection"] = llm_spans["output"].map(
        extract_tool_selection
    )
    return llm_spans[llm_spans["tool_selection"].notna()].drop(
        columns=["output"]
    )


def serialize_tool_definitions(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def build_tool_evaluators():
    judge_llm = LLM(provider="litellm", model=settings.llm_model)
    input_mapping = {
        "input": "input",
        "available_tools": lambda row: serialize_tool_definitions(
            row["available_tools"]
        ),
        "tool_selection": "tool_selection",
    }
    return [
        bind_evaluator(
            evaluator=ToolSelectionEvaluator(llm=judge_llm, temperature=0.0),
            input_mapping=input_mapping,
        ),
        bind_evaluator(
            evaluator=ToolInvocationEvaluator(llm=judge_llm, temperature=0.0),
            input_mapping=input_mapping,
        ),
    ]


async def evaluate_tool_spans(conversation_ids: set[str]):

    await asyncio.sleep(2)
    llm_spans = load_llm_spans(conversation_ids)
    if llm_spans.empty:
        print(f"No LLM spans found in project when evaluating tool spans: {conversation_ids}")
        return llm_spans

    return await async_evaluate_dataframe(
        dataframe=llm_spans,
        evaluators=build_tool_evaluators(),
        concurrency=EVALUATION_CONCURRENCY,
    )


def upload_evaluations(evaluations) -> int:
    annotations = to_annotation_dataframe(dataframe=evaluations)
    if annotations.empty:
        return 0

    phx_client = Client(base_url=settings.phoenix_base_url)
    phx_client.spans.log_span_annotations_dataframe(
        dataframe=annotations,
        sync=True,
    )
    return len(annotations)


async def generate_evaluation_spans() -> set[str]:
    tools = await load_tool_schemas()
    conversation_ids = set()

    with phoenix_observability(settings) as tracer_provider:
        runner = AgentRunner(tracer_provider=tracer_provider)
        for question in agent_questions:
            conversation_id = f"eval-{uuid4()}"
            conversation_ids.add(conversation_id)
            store = FakeSallaStore(DEFAULT_FIXTURE)
            try:
                with agent_turn_span(
                    tracer_provider,
                    conversation_id=conversation_id,
                    query=question,
                    model=settings.llm_model,
                    prompt_version=SYSTEM_PROMPT_VERSION,
                    mode="evaluation",
                ) as span:
                    result = await runner.run(
                        [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": question},
                        ],
                        tools,
                        store.execute_tool,
                    )
                    answer = result[-1].get("content") or ""
                    if span is not None:
                        span.set_output(answer, mime_type="text/plain")
            except Exception as e:
                print(f"Error running agent: {e}")
                continue
    return conversation_ids


async def main():
    conversation_ids = await generate_evaluation_spans()
    evaluations = await evaluate_tool_spans(conversation_ids)
    if not evaluations.empty:
        uploaded_count = upload_evaluations(evaluations)
        print(
            f"Uploaded {uploaded_count} evaluation annotations to Phoenix project "
            f"{settings.phoenix_project_name!r}"
        )
    return evaluations


if __name__ == "__main__":
    evaluations = asyncio.run(main())
    if evaluations.empty:
        print(
            "No evaluable LLM spans found in project "
            f"{settings.phoenix_project_name!r}"
        )
    else:
        score_columns = ["tool_selection_score", "tool_invocation_score"]
        print(evaluations[score_columns].head())
