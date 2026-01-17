ADMIN_ID = 6759780449 # id
STATS_CHANNEL_ID = -1003023115181 # айди поста со статистикой
STATS_MESSAGE_ID = 4 # пост со статистикой
STATS_UPDATE_INTERVAL_SEC = 180
DATABASE_NAME = 'dating.db' # база данных

# вместо цифр вставить корпуса колледжей
COLLEGES = [
    "0",
    "1",
    "2",
    "3"
]

# Индексы колледжей для удобства использования
COLLEGE_0 = 0 # для удобства надо указать колледж
COLLEGE_1 = 1
COLLEGE_2 = 2
COLLEGE_3 = 3

COLLEGE_DISTANCES = {
    (COLLEGE_3, COLLEGE_0): 20,
    (COLLEGE_0, COLLEGE_3): 20,
    (COLLEGE_3, COLLEGE_1): 15,
    (COLLEGE_1, COLLEGE_3): 15,
    (COLLEGE_3, COLLEGE_2): 18,
    (COLLEGE_2, COLLEGE_3): 18,
    (COLLEGE_0, COLLEGE_1): 8,
    (COLLEGE_1, COLLEGE_0): 8,
    (COLLEGE_0, COLLEGE_2): 10,
    (COLLEGE_2, COLLEGE_0): 10,
    (COLLEGE_1, COLLEGE_2): 5,
    (COLLEGE_2, COLLEGE_1): 5
}

BOT_TOKEN = "" # token
