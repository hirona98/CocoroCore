"""config_validator.py のユニットテスト"""
import unittest

from config_validator import validate_config


class TestValidateConfig(unittest.TestCase):
    """validate_config 関数のテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.valid_config = {
            "characterList": [
                {
                    "isUseLLM": True,
                    "apiKey": "valid-api-key",
                    "isUseSTT": True,
                    "sttApiKey": "valid-stt-key",
                    "sttEngine": "amivoice"
                }
            ],
            "cocoroCorePort": 55601,
            "cocoroDockPort": 55600,
            "cocoroMemoryPort": 55602,
            "cocoroShellPort": 55605
        }

    def test_validate_config_valid(self):
        """有効な設定の検証テスト"""
        warnings = validate_config(self.valid_config)
        self.assertEqual(len(warnings), 0)

    def test_validate_config_no_character_list(self):
        """characterListがない場合のテスト"""
        config = {}
        warnings = validate_config(config)
        
        self.assertIn("characterListが設定されていません", warnings)

    def test_validate_config_empty_character_list(self):
        """空のcharacterListの場合のテスト"""
        config = {"characterList": []}
        warnings = validate_config(config)
        
        self.assertIn("characterListが設定されていません", warnings)

    def test_validate_config_missing_api_key(self):
        """LLM有効だがAPIキーがない場合のテスト"""
        config = {
            "characterList": [
                {
                    "isUseLLM": True,
                    # apiKey がない
                }
            ]
        }
        warnings = validate_config(config)
        
        self.assertIn("キャラクター0: LLMが有効ですがAPIキーが設定されていません", warnings)

    def test_validate_config_llm_disabled_no_warning(self):
        """LLM無効の場合はAPIキーなしでも警告なしのテスト"""
        config = {
            "characterList": [
                {
                    "isUseLLM": False,
                    # apiKey がない
                }
            ]
        }
        warnings = validate_config(config)
        
        # LLM関連の警告がないことを確認
        llm_warnings = [w for w in warnings if "LLMが有効ですが" in w]
        self.assertEqual(len(llm_warnings), 0)

    def test_validate_config_missing_stt_api_key(self):
        """STT有効だがAPIキーがない場合のテスト"""
        config = {
            "characterList": [
                {
                    "isUseSTT": True,
                    # sttApiKey がない
                }
            ]
        }
        warnings = validate_config(config)
        
        self.assertIn("キャラクター0: STTが有効ですがAPIキーが設定されていません", warnings)

    def test_validate_config_stt_disabled_no_warning(self):
        """STT無効の場合はAPIキーなしでも警告なしのテスト"""
        config = {
            "characterList": [
                {
                    "isUseSTT": False,
                    # sttApiKey がない
                }
            ]
        }
        warnings = validate_config(config)
        
        # STT関連の警告がないことを確認
        stt_warnings = [w for w in warnings if "STTが有効ですが" in w]
        self.assertEqual(len(stt_warnings), 0)

    def test_validate_config_invalid_stt_engine(self):
        """無効なSTTエンジンの場合のテスト"""
        config = {
            "characterList": [
                {
                    "isUseSTT": True,
                    "sttApiKey": "valid-key",
                    "sttEngine": "invalid_engine"
                }
            ]
        }
        warnings = validate_config(config)
        
        self.assertTrue(any("不正なSTTエンジン 'invalid_engine'" in w for w in warnings))

    def test_validate_config_valid_stt_engines(self):
        """有効なSTTエンジンの場合のテスト"""
        valid_engines = ["amivoice", "openai", "AMIVOICE", "OPENAI"]
        
        for engine in valid_engines:
            with self.subTest(engine=engine):
                config = {
                    "characterList": [
                        {
                            "isUseSTT": True,
                            "sttApiKey": "valid-key",
                            "sttEngine": engine
                        }
                    ]
                }
                warnings = validate_config(config)
                
                # STTエンジン関連の警告がないことを確認
                engine_warnings = [w for w in warnings if "不正なSTTエンジン" in w]
                self.assertEqual(len(engine_warnings), 0)

    def test_validate_config_default_stt_engine(self):
        """デフォルトSTTエンジンの場合のテスト"""
        config = {
            "characterList": [
                {
                    "isUseSTT": True,
                    "sttApiKey": "valid-key",
                    # sttEngine がない（デフォルト値を使用）
                }
            ]
        }
        warnings = validate_config(config)
        
        # STTエンジン関連の警告がないことを確認
        engine_warnings = [w for w in warnings if "不正なSTTエンジン" in w]
        self.assertEqual(len(engine_warnings), 0)

    def test_validate_config_invalid_port_numbers(self):
        """無効なポート番号の場合のテスト"""
        invalid_ports = [
            ("cocoroCorePort", 1023),    # 小さすぎる
            ("cocoroDockPort", 65536),   # 大きすぎる
            ("cocoroMemoryPort", -1),    # 負の値
            ("cocoroShellPort", "8080"), # 文字列
        ]
        
        for port_name, port_value in invalid_ports:
            with self.subTest(port_name=port_name, port_value=port_value):
                config = {
                    "characterList": [{}],
                    port_name: port_value
                }
                warnings = validate_config(config)
                
                self.assertTrue(any(f"{port_name}: 無効なポート番号" in w for w in warnings))

    def test_validate_config_valid_port_numbers(self):
        """有効なポート番号の場合のテスト"""
        config = {
            "characterList": [{}],
            "cocoroCorePort": 8080,
            "cocoroDockPort": 3000,
            "cocoroMemoryPort": 5432,
            "cocoroShellPort": 65535
        }
        warnings = validate_config(config)
        
        # ポート関連の警告がないことを確認
        port_warnings = [w for w in warnings if "無効なポート番号" in w]
        self.assertEqual(len(port_warnings), 0)

    def test_validate_config_default_ports(self):
        """デフォルトポートの場合のテスト"""
        config = {
            "characterList": [{}]
            # ポート設定なし（デフォルト値を使用）
        }
        warnings = validate_config(config)
        
        # ポート関連の警告がないことを確認
        port_warnings = [w for w in warnings if "無効なポート番号" in w]
        self.assertEqual(len(port_warnings), 0)

    def test_validate_config_multiple_characters(self):
        """複数キャラクターの検証テスト"""
        config = {
            "characterList": [
                {
                    "isUseLLM": True,
                    "apiKey": "valid-key-1"
                },
                {
                    "isUseLLM": True,
                    # apiKey がない
                },
                {
                    "isUseSTT": True,
                    "sttApiKey": "valid-stt-key"
                },
                {
                    "isUseSTT": True,
                    # sttApiKey がない
                }
            ]
        }
        warnings = validate_config(config)
        
        # キャラクター1のLLM警告
        self.assertIn("キャラクター1: LLMが有効ですがAPIキーが設定されていません", warnings)
        # キャラクター3のSTT警告
        self.assertIn("キャラクター3: STTが有効ですがAPIキーが設定されていません", warnings)

    def test_validate_config_comprehensive(self):
        """包括的な検証テスト"""
        config = {
            "characterList": [
                {
                    "isUseLLM": True,
                    # apiKey がない
                    "isUseSTT": True,
                    # sttApiKey がない
                    "sttEngine": "invalid_engine"
                }
            ],
            "cocoroCorePort": 1023,  # 無効
            "cocoroDockPort": "invalid"  # 無効
        }
        warnings = validate_config(config)
        
        # 複数の警告が含まれることを確認
        self.assertGreater(len(warnings), 3)
        
        # 各種警告の存在確認
        warning_text = " ".join(warnings)
        self.assertIn("LLMが有効ですがAPIキーが設定されていません", warning_text)
        self.assertIn("STTが有効ですがAPIキーが設定されていません", warning_text)
        self.assertIn("不正なSTTエンジン", warning_text)
        self.assertIn("無効なポート番号", warning_text)

    def test_validate_config_empty_config(self):
        """完全に空の設定の場合のテスト"""
        config = {}
        warnings = validate_config(config)
        
        # characterListの警告は確実に含まれる
        self.assertIn("characterListが設定されていません", warnings)

    def test_validate_config_none_values(self):
        """None値が含まれる場合のテスト"""
        config = {
            "characterList": None
        }
        # 現在の実装ではTypeErrorが発生する
        with self.assertRaises(TypeError):
            validate_config(config)

    def test_validate_config_return_type(self):
        """戻り値の型確認テスト"""
        config = self.valid_config
        warnings = validate_config(config)
        
        self.assertIsInstance(warnings, list)
        for warning in warnings:
            self.assertIsInstance(warning, str)


if __name__ == '__main__':
    unittest.main()