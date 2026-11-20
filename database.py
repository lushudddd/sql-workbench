import re
from contextlib import closing


ORACLE_TOKEN = re.compile(
    r"\b(?:n?q)'[^\s]|--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\""
    r"|^[ \t]*/[ \t]*(?=\r?$)|;|[a-z][\w$#]*|[^\s]",
    re.I | re.M | re.S,
)
PLSQL = re.compile(
    r"^(?:DECLARE|BEGIN|WITH (?:FUNCTION|PROCEDURE)|"
    r"CREATE (?:OR REPLACE )?(?:(?:NON)?EDITIONABLE )?"
    r"(?:PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE))$",
    re.I,
)
PREVIEW_ROWS = 500


def oracle_statements(script):
    start = position = 0
    first = None
    words = []
    block = False
    while match := ORACLE_TOKEN.search(script, position):
        token = match.group()
        position = match.end()
        if token.startswith(("--", "/*")):
            continue
        if re.fullmatch(r"\s*/\s*", token):
            if first is not None:
                sql = script[start:match.start()].strip()
                yield script.count("\n", 0, first) + 1, sql
            start, first, words, block = position, None, [], False
            continue
        if token == ";" and not block:
            if first is not None:
                yield script.count("\n", 0, first) + 1, script[start:match.start()].strip()
            start, first, words = position, None, []
            continue
        if first is None:
            first = match.start()
        if len(words) < 6:
            words.append(token)
            block = block or bool(PLSQL.fullmatch(" ".join(words)))
        if re.fullmatch(r"(?:n?q)'[^\s]", token, re.I):
            opening = token[-1]
            ending = dict(zip("[{(<", "]})>")).get(opening, opening) + "'"
            end = script.find(ending, position)
            if end < 0:
                raise ValueError("Oracle q 引用字符串缺少结束符")
            position = end + len(ending)
    if first is not None:
        yield script.count("\n", 0, first) + 1, script[start:].strip()


def connect(profile, password):
    host, port = profile["host"], int(profile["port"])
    credentials = {"user": profile["user"], "password": password}
    if profile["engine"] == "MySQL":
        import mysql.connector

        return mysql.connector.connect(
            host=host, port=port, database=profile["target"] or None,
            connection_timeout=8, read_timeout=120, write_timeout=120,
            allow_local_infile=False, **credentials,
        )

    import oracledb

    connection = oracledb.connect(
        host=host, port=port, service_name=profile["target"],
        tcp_connect_timeout=8, **credentials,
    )
    connection.call_timeout = 120_000
    return connection


def publish_result(cursor, publish, line=None):
    if not cursor.description:
        count = cursor.rowcount
        publish((), (), f"影响行数 {count}" if count >= 0 else "执行成功", line)
        return
    columns = tuple(column[0] for column in cursor.description)
    rows = []
    count = 0
    while batch := cursor.fetchmany(200):
        remaining = max(0, PREVIEW_ROWS - count)
        rows.extend(tuple("NULL" if value is None else str(value) for value in row)
                    for row in batch[:remaining])
        count += len(batch)
    publish(columns, rows, f"{count} 行，显示 {len(rows)} 行", line)


def run(connection, engine, script, publish, stop):
    with closing(connection.cursor()) as cursor:
        if engine == "MySQL":
            cursor.execute(script)
            while True:
                publish_result(cursor, publish)
                if stop.is_set() or not cursor.nextset():
                    return
        else:
            statements = list(oracle_statements(script))
            for line, statement in statements:
                if stop.is_set():
                    return
                try:
                    cursor.execute(statement)
                    publish_result(cursor, publish, line)
                    sql = re.sub(r"^(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)+", "",
                                 statement, flags=re.S)
                    if re.match(r"(?:BEGIN|DECLARE)\b", sql, re.I):
                        for implicit in cursor.getimplicitresults():
                            with closing(implicit):
                                publish_result(implicit, publish, line)
                except Exception as error:
                    raise ValueError(f"脚本第 {line} 行开始的语句执行失败\n{error}") from error
