# src/dkh/application/services/classifier.py
# encoding: utf-8
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import structlog

from ...domain.models import ClassificationResult, Message, ValidationStatus
from ...domain.ports import ValidatorPort

logger = structlog.get_logger(__name__)


class GPTClassifier:
    """
    Адаптер, який використовує ValidatorPort для класифікації повідомлень.
    """

    def __init__(self, validator: ValidatorPort):
        self._validator = validator

    async def classify(self, msg: Message) -> ClassificationResult:
        try:
            validation_result = await self._validator.validate(msg)
            is_opportunity = validation_result.status == ValidationStatus.OK
            return ClassificationResult(
                is_opportunity=is_opportunity,
                relevance=int(validation_result.score),
                reason='' if is_opportunity else 'validation_failed',
            )
        except Exception as e:
            logger.error('classification_error', error=str(e), exc_info=True)
            return ClassificationResult(
                is_opportunity=False, relevance=0, reason='classification_exception'
            )


class ExcelFileClassifier:
    """
    Сервіс, який використовує класифікатор для обробки рядків з Excel-файлу.
    """

    def __init__(self, classifier: GPTClassifier, xlsx_path: Path):
        self.classifier = classifier
        self.xlsx_path = xlsx_path

    async def run(self, sheet_in: str = 'All messages', sheet_out: str = 'Classification') -> None:
        """Читає лист, класифікує кожен рядок і записує результати в новий лист."""
        logger.info('starting_file_classification', path=str(self.xlsx_path))
        try:
            df = pd.read_excel(self.xlsx_path, sheet_name=sheet_in, engine='openpyxl')
        except FileNotFoundError:
            logger.error('excel_file_not_found', path=str(self.xlsx_path))
            return
        except Exception as e:
            logger.error('excel_read_failed', error=str(e), path=str(self.xlsx_path))
            return

        results: List[ClassificationResult] = []
        for _, row in df.iterrows():
            content = str(row.get('content', ''))
            if not content.strip():
                results.append(
                    ClassificationResult(is_opportunity=False, relevance=0, reason='empty_content')
                )
                continue

            msg = Message(
                message_id=0,
                channel_id=0,
                guild_id=None,
                author_id=0,
                author_name='',
                content=content,
                timestamp=datetime.utcnow(),  # якщо немає, даємо now
                jump_url='',
                keyword=None,
                guild_name='',
            )
            res = await self.classifier.classify(msg)
            results.append(res)

        df['status'] = ['yes' if r.is_opportunity else 'no' for r in results]
        df['relevance'] = [r.relevance for r in results]
        df['reason'] = [r.reason for r in results]

        try:
            with pd.ExcelWriter(
                self.xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='replace'
            ) as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_out)
            logger.info(
                'classification_complete', output_sheet=sheet_out, path=str(self.xlsx_path)
            )
        except Exception as e:
            logger.error('excel_write_failed', error=str(e), path=str(self.xlsx_path))
