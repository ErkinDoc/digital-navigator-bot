# ... (весь код из предыдущей версии, только добавил эти строки в нужные места)

# После отправки якорного файла (если это чек-лист — добавляем призыв)
@dp.message(NavigatorStates.waiting_category_text)
async def process_category_text(message: types.Message, state: FSMContext):
    # ... (существующий код)
    if os.path.exists(file_path):
        await bot.send_document(message.chat.id, FSInputFile(file_path))
    else:
        await message.answer("⚠️ Файл временно недоступен.")
    
    # Новый призыв после якоря
    keyboard_checklist = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Прислать заполненный чек-лист доктору", url="https://t.me/DrErkin")]
    ])
    await message.answer(
        "Заполните чек-лист и пришлите мне — я лично проанализирую и дам точные рекомендации.",
        reply_markup=keyboard_checklist
    )

    # ... (остальное без изменений)

# После углубления (реакция)
@dp.callback_query(NavigatorStates.waiting_reaction, lambda c: c.data.startswith("reaction_"))
async def process_reaction(callback: types.CallbackQuery, state: FSMContext):
    # ... (существующий код)
    
    # Новый призыв после углубления
    keyboard_checklist = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Прислать заполненный чек-лист доктору", url="https://t.me/DrErkin")]
    ])
    await callback.message.answer(
        "Если заполнили чек-лист — пришлите мне, я дам персональную интерпретацию и рекомендации.",
        reply_markup=keyboard_checklist
    )
    
    # ... (дополнительные файлы и переход)

# В самостоятельном пути (после премиум-подборки)
@dp.callback_query(NavigatorStates.waiting_path, lambda c: c.data == "path_self")
async def path_self(callback: types.CallbackQuery, state: FSMContext):
    # ... (существующий код)
    
    keyboard_checklist = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Прислать заполненный чек-лист доктору", url="https://t.me/DrErkin")]
    ])
    await callback.message.answer(
        "Эти материалы для самостоятельной работы. Если заполнили чек-лист — пришлите мне для точной интерпретации.",
        reply_markup=keyboard_checklist
    )

# ... (остальной код без изменений, включая игнор файлов и хендлер на запись)
