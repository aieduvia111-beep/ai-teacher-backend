import json
import re
from openai import AsyncOpenAI
from .config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def fix_latex_dollars(text: str) -> str:
    """Naprawia LaTeX - dodaje dolary i normalizuje backslashe"""
    if not text:
        return text

    # Normalizuj podwojne backslashe -> pojedyncze (AI czasem zwraca \\frac zamiast \frac)
    text = text.replace('\\\\', '\\')

    # Wstaw spacje miedzy cyfra/litera a komenda: 3\frac -> 3 \frac
    text = re.sub(r'([0-9a-zA-Z])(\\[a-zA-Z])', r'\1 \2', text)

    # Zachowaj istniejace $...$ i $$...$$
    parts = []
    last = 0
    for m in re.finditer(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', text):
        parts.append(('fix', text[last:m.start()]))
        parts.append(('keep', m.group()))
        last = m.end()
    parts.append(('fix', text[last:]))

    result = []
    for kind, part in parts:
        if kind == 'keep':
            result.append(part)
        else:
            # Otocz dolarami kazda komende LaTeX: \frac{}{}, \sqrt{}, \pi, \times itp.
            fixed = re.sub(
                r'\\[a-zA-Z]+(?:\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}|\[[^\]]*\])*(?:[_^](?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|[a-zA-Z0-9]))*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})?',
                lambda m: '$' + m.group(0) + '$',
                part
            )
            result.append(fixed)

    return ''.join(result)

def fix_problem(p: dict) -> dict:
    if not isinstance(p, dict):
        return p
    if 'question' in p:
        p['question'] = fix_latex_dollars(p['question'])
    if 'solution' in p and isinstance(p['solution'], dict):
        sol = p['solution']
        sol['steps'] = [fix_latex_dollars(s) for s in sol.get('steps', [])]
        for field in ('final_answer', 'explanation', 'alternative_method'):
            if field in sol:
                sol[field] = fix_latex_dollars(sol[field])
    if 'similar_problems' in p:
        p['similar_problems'] = [fix_latex_dollars(s) for s in p.get('similar_problems', [])]
    return p


def build_prompt(subject: str, mode: str, generate_similar: bool, show_explanation: bool) -> str:
    subject_rules = {
        "matematyka": r"WSZYSTKIE wyrazenia matematyczne w LaTeX z dolarami: $x^2$, $\frac{a}{b}$, $\sqrt{x}$, $\log_2 8$.",
        "fizyka": r"Wzory fizyczne w LaTeX z dolarami: $F=ma$, $v^2=v_0^2+2as$. Podaj jednostki.",
        "chemia": "Rownania chemiczne, wzory sumaryczne, stechiometria.",
        "biologia": "Opisz procesy biologiczne, nazwy lacinskie jezeli istotne.",
        "historia": "Podaj daty, postaci, zwiazki przyczynowo-skutkowe.",
        "polski": "Analizuj jezyk, stylistyke, srodki wyrazu.",
        "angielski": "Correct grammar, explain rules in Polish.",
        "inne": "Odpowiedz merytorycznie na zadane pytanie.",
    }

    mode_instruction = {
        "solve": "Rozwiaz kazde zadanie krok po kroku z pelnymi obliczeniami.",
        "check": "Sprawdz czy rozwiazania sa poprawne. Znajdz bledy i popraw je.",
        "explain": "Wyjasni temat ogolnie, nie rozwiazuj zadan.",
        "grade": "Ocen rozwiazanie ucznia. Napisz co jest dobrze, co zle, ile punktow by dostal (0-10).",
    }.get(mode, "Rozwiaz kazde zadanie krok po kroku.")

    similar_instruction = (
        r'"similar_problems": ["Konkretne zadanie z liczbami np. Oblicz 25% z 320 zl", "Inne konkretne zadanie z liczbami"]'
        if generate_similar else r'"similar_problems": []'
    )

    explanation_field = "Krotkie wyjasnienie teorii" if show_explanation else ""

    return (
        f"Jestes ekspertem z przedmiotu: {subject}.\n\n"
        "WAZNE - PRZECZYTAJ UWAZANIE:\n"
        "Przejrzyj cale zdjecie od gory do dolu.\n"
        "Znajdz WSZYSTKIE zadania - sa oznaczone 'Zadanie 1', 'Zadanie 2' itd.\n"
        "Czesto ostatnie zadanie jest na dole strony - nie pomijaj go!\n"
        "Policz ile jest zadań i rozwiaz KAZDE z nich.\n\n"
        f"{mode_instruction}\n\n"
        "FORMATOWANIE:\n"
        f"{subject_rules.get(subject, '')}\n"
        "- KAZDY wzor MUSI byc w $...$ np: $\\frac{10}{3}$\n\n"
        "ODPOWIEDZ W JSON:\n"
        "{\n"
        '  "problems": [\n'
        "    {\n"
        '      "question": "Tresc zadania z numerem",\n'
        '      "solution": {\n'
        '        "steps": ["Krok 1: ...", "Krok 2: ..."],\n'
        '        "final_answer": "Odpowiedz",\n'
        f'        "explanation": "{explanation_field}",\n'
        '        "alternative_method": ""\n'
        "      },\n"
        f"      {similar_instruction}\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "ZASADY:\n"
        "- Po polsku. TYLKO JSON.\n"
        "- NIE POMIJAJ zadania ostatniego na stronie!\n"
        "- Jesli widzisz 6 zadan na zdjeciu - w JSON musi byc 6 obiektow\n"
        "- Jesli widzisz 5 zadan - 5 obiektow. Itd.\n"
        "- Podpunkty A B C D to jedno zadanie\n"
        "- similar_problems: konkretne zadania z liczbami, nie nazwy tematow"
    )



async def analyze_image_with_gpt4_vision(image_data: str, prompt: str = None) -> str:
    if not prompt:
        prompt = "Przeanalizuj zdjecie i rozwiaz zadania. Wzory w LaTeX z dolarami. Po polsku."
    if "base64," in image_data:
        image_data = image_data.split("base64,")[1]
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}", "detail": "high"}}
        ]}],
        max_tokens=2000, temperature=0.5
    )
    return response.choices[0].message.content


async def vision_analyze_homework(image_data: str) -> str:
    return await analyze_image_with_gpt4_vision(image_data, "Sprawdz prace domowa: co poprawne, bledy, jak naprawic, ocena 1-10. Po polsku.")


async def vision_analyze_diagram(image_data: str) -> str:
    return await analyze_image_with_gpt4_vision(image_data, "Przeanalizuj diagram. Po polsku.")


async def solve_homework_vision(
    image_base64: str,
    subject: str = "matematyka",
    mode: str = "solve",
    show_steps: bool = True,
    generate_similar: bool = True,
    show_explanation: bool = True,
) -> dict:
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]

    prompt = build_prompt(subject, mode, generate_similar, show_explanation)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "high"}}
            ]}],
            max_tokens=8000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        data["success"] = True

        if data.get("problems"):
            data["problems"] = [fix_problem(p) for p in data["problems"]]
            print(f"DEBUG: {repr(data['problems'][0].get('question','')[:60])}")

        if not data.get("problems"):
            print("Retry...")
            r2 = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "high"}}
                ]}],
                max_tokens=8000, temperature=0.1,
            )
            raw2 = r2.choices[0].message.content
            s = raw2.find('{')
            e = raw2.rfind('}') + 1
            if s != -1 and e > s:
                try:
                    d2 = json.loads(raw2[s:e])
                    if d2.get("problems"):
                        d2["problems"] = [fix_problem(p) for p in d2["problems"]]
                        data = d2
                        data["success"] = True
                except Exception:
                    pass

        print(f"Vision solve: {len(data.get('problems', []))} problemow")
        return data

    except Exception as e:
        print(f"Vision error: {e}")
        return {"success": False, "error": str(e), "problems": []}
