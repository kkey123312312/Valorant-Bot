def reply(user_text: str) -> str:
    """Заглушка вместо модели: повторяет фразу пользователя."""
    return f"Ты сказал: {user_text}"


def main() -> None:
    history: list[dict[str, str]] = []

    while True:
        user_text = input("Вы: ").strip()

        if user_text.lower() == "выход":
            break

        if not user_text:
            continue

        history.append({"role": "user", "content": user_text})
        assistant_text = reply(user_text)
        history.append({"role": "assistant", "content": assistant_text})
        print(f"Ассистент: {assistant_text}")


if __name__ == "__main__":
    main()
