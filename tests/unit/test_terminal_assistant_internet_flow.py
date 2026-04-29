from core import atena_terminal_assistant as ta


def test_is_internet_request_plain_pesquisa():
    assert ta._is_internet_request("pesquisa pra mim que dia o flamengo joga") is True


def test_is_internet_request_with_ask_prefix():
    assert ta._is_internet_request("ask atena pesquisa pra mim que dia o brasil joga") is True


def test_is_web_fact_question_detects_sports():
    assert ta._is_web_fact_question("quando o flamengo joga?") is True


def test_extract_topic_removes_fillers():
    assert ta._extract_internet_topic("pesquisa pra mim que dia o flamengo joga") == "que dia flamengo joga"


def test_extract_topic_removes_ask_prefix():
    assert ta._extract_internet_topic("ask atena: pesquisa pra mim que dia o brasil joga") == "que dia brasil joga"


def test_run_user_internet_research_empty_topic_guidance():
    assert "`/internet <tema>`" in ta.run_user_internet_research("/internet")
