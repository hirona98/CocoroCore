"""image_processor.py のテスト"""


from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from image_processor import generate_image_description, parse_image_response


class TestParseImageResponse:
    """画像レスポンス解析のテスト"""

    def test_parse_image_response_basic(self):
        """基本的な画像レスポンス解析テスト"""
        response_text = "説明: これは猫の画像です。白い毛色で、青い目をしています。\n分類: 動物 / 静か / 昼"
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert "description" in result
        assert "category" in result
        assert "猫" in result["description"]
        assert "動物" in result["category"]

    def test_parse_image_response_empty(self):
        """空のレスポンス解析テスト"""
        response_text = ""
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert result["description"] == ""
        assert result["category"] == ""

    def test_parse_image_response_none(self):
        """Noneレスポンス解析テスト"""
        response_text = None
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert result["description"] == ""
        assert result["category"] == ""

    def test_parse_image_response_long_text(self):
        """長いテキストの解析テスト"""
        response_text = "説明: " + "これは非常に長い説明です。" * 100
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert len(result["description"]) > 0

    def test_parse_image_response_special_characters(self):
        """特殊文字を含むレスポンス解析テスト"""
        response_text = "説明: 画像には特殊文字が含まれています: !@#$%^&*()_+{}|:<>?[]\\;'\",./"
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert "特殊文字" in result["description"]

    def test_parse_image_response_unicode(self):
        """Unicode文字を含むレスポンス解析テスト"""
        response_text = "説明: 画像には絵文字が含まれています: 😀🎉🚀🌈"
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert "絵文字" in result["description"]

    def test_parse_image_response_multiline(self):
        """複数行のレスポンス解析テスト"""
        response_text = """説明: これは複数行の画像説明です。
分類: テスト / 静か / 昼"""
        
        result = parse_image_response(response_text)
        
        assert isinstance(result, dict)
        assert "複数行" in result["description"]
        assert "テスト" in result["category"]


class TestGenerateImageDescription:
    """画像説明生成のテスト"""

    @pytest.mark.asyncio
    async def test_generate_image_description_basic(self):
        """基本的な画像説明生成テスト"""
        with patch('litellm.acompletion') as mock_completion:
            # モックレスポンスを設定
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "説明: これは猫の画像です。"
            mock_completion.return_value = mock_response
            
            image_urls = ["https://example.com/image.jpg"]
            config = {
                "characterList": [{"apiKey": "test_key", "llmModel": "gpt-4-vision-preview"}],
                "currentCharacterIndex": 0
            }
            
            result = await generate_image_description(image_urls, config)
            
            assert isinstance(result, str)
            assert "猫" in result
            mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_image_description_empty_urls(self):
        """空のURLリストでのテスト"""
        image_urls = []
        config = {}
        
        result = await generate_image_description(image_urls, config)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_image_description_error_handling(self):
        """エラーハンドリングのテスト"""
        with patch('litellm.acompletion') as mock_completion:
            # API呼び出しでエラーが発生する場合
            mock_completion.side_effect = Exception("API Error")
            
            image_urls = ["https://example.com/image.jpg"]
            config = {
                "characterList": [{"apiKey": "test_key", "llmModel": "gpt-4-vision-preview"}],
                "currentCharacterIndex": 0
            }
            
            result = await generate_image_description(image_urls, config)
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_image_description_no_api_key(self):
        """APIキーがない場合のテスト"""
        image_urls = ["https://example.com/image.jpg"]
        config = {
            "characterList": [{"llmModel": "gpt-4-vision-preview"}],
            "currentCharacterIndex": 0
        }
        
        result = await generate_image_description(image_urls, config)
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_image_description_multiple_images(self):
        """複数画像での説明生成テスト"""
        with patch('litellm.acompletion') as mock_completion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "説明: 複数の画像です。"
            mock_completion.return_value = mock_response
            
            image_urls = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
            config = {
                "characterList": [{"apiKey": "test_key", "llmModel": "gpt-4-vision-preview"}],
                "currentCharacterIndex": 0
            }
            
            result = await generate_image_description(image_urls, config)
            
            assert isinstance(result, str)
            assert "複数" in result
            mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_image_description_different_models(self):
        """異なるモデルでの画像説明生成テスト"""
        models_to_test = [
            "gpt-4-vision-preview",
            "gpt-4o",
            "claude-3-sonnet-20240229"
        ]
        
        for model in models_to_test:
            with patch('litellm.acompletion') as mock_completion:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = MagicMock()
                mock_response.choices[0].message.content = f"説明: Model {model} の説明です。"
                mock_completion.return_value = mock_response
                
                image_urls = ["https://example.com/image.jpg"]
                config = {
                    "characterList": [{"apiKey": "test_key", "llmModel": model}],
                    "currentCharacterIndex": 0
                }
                
                result = await generate_image_description(image_urls, config)
                
                assert isinstance(result, str)
                assert len(result) > 0
                mock_completion.assert_called_once()


class TestImageProcessorIntegration:
    """image_processor 統合テスト"""

    def test_module_imports_successfully(self):
        """モジュールが正常にインポートできることを確認"""
        try:
            from image_processor import generate_image_description, parse_image_response
            assert callable(parse_image_response)
            assert callable(generate_image_description)
            success = True
        except ImportError:
            success = False
        
        assert success, "image_processor モジュールのインポートに失敗"

    def test_parse_and_generate_integration(self):
        """parse_image_responseとgenerate_image_descriptionの統合テスト"""
        # parse_image_responseの動作確認
        test_response = "説明: これはテスト画像の説明です。\n分類: テスト / 静か / 昼"
        parsed_result = parse_image_response(test_response)
        
        assert isinstance(parsed_result, dict)
        assert "テスト" in parsed_result["description"]

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """完全なワークフローのシミュレーションテスト"""
        with patch('litellm.acompletion') as mock_completion:
            # 1. 画像説明生成のモック
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "説明: これは美しい風景の画像です。\n分類: 風景 / 美しい / 昼"
            mock_completion.return_value = mock_response
            
            # 2. 画像説明生成を実行
            image_urls = ["https://example.com/landscape.jpg"]
            config = {
                "characterList": [{"apiKey": "test_key", "llmModel": "gpt-4-vision-preview"}],
                "currentCharacterIndex": 0
            }
            
            description = await generate_image_description(image_urls, config)
            
            # 3. レスポンスを解析
            parsed_description = parse_image_response(description)
            
            # 4. 結果の検証
            assert isinstance(description, str)
            assert isinstance(parsed_description, dict)
            assert len(description) > 0
            assert "風景" in parsed_description["description"]

    def test_error_resilience(self):
        """エラー耐性のテスト"""
        # parse_image_responseは様々な入力に対して堅牢であることを確認
        test_inputs = [
            None,
            "",
            "正常な説明",
            "特殊文字!@#$%",
            "😀🎉絵文字",
            "\n\t空白文字\r\n",
            "非常に長い文字列" * 1000
        ]
        
        for test_input in test_inputs:
            try:
                result = parse_image_response(test_input)
                assert isinstance(result, dict)
                success = True
            except Exception as e:
                success = False
                pytest.fail(f"入力 '{test_input}' でエラーが発生: {e}")
            
            assert success

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """同時リクエストのテスト"""
        import asyncio
        
        with patch('litellm.acompletion') as mock_completion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "説明: 並行処理テストの画像説明"
            mock_completion.return_value = mock_response
            
            # 複数の同時リクエストを作成
            tasks = []
            config = {
                "characterList": [{"apiKey": "test_key", "llmModel": "gpt-4-vision-preview"}],
                "currentCharacterIndex": 0
            }
            
            for i in range(5):
                task = generate_image_description(
                    [f"https://example.com/image{i}.jpg"],
                    config
                )
                tasks.append(task)
            
            # すべてのタスクを同時実行
            results = await asyncio.gather(*tasks)
            
            # すべてのリクエストが成功することを確認
            assert len(results) == 5
            for result in results:
                assert isinstance(result, str)
                assert len(result) > 0