from aiogram.fsm.state import State, StatesGroup

class StartState(StatesGroup):
    opening_stock = State()

class SaleState(StatesGroup):
    cash = State()
    card = State()

class ExpenseState(StatesGroup):
    amount = State()
    note = State()

class PurchaseState(StatesGroup):
    amount = State()
    note = State()

class CloseState(StatesGroup):
    closing_stock = State()
