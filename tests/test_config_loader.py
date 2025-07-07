"""config_loader.py のユニットテスト"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, mock_open
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_loader import load_config, parse_args


class TestConfigLoader(unittest.TestCase):
    """config_loader モジュールのテストクラス"""

    def setUp(self):
        """各テストの前処理"""
        # テスト用の設定データ
        self.test_config = {
            "CharacterName": "TestCharacter",
            "LLMProvider": "openai",
            "apiUrl": "http://localhost:55601",
            "ports": {
                "CocoroCore": 55601,
                "ChatMemory": 55602,
                "CocoroDock": 55600
            }
        }

    def test_parse_args_no_arguments(self):
        """引数なしでparse_argsをテスト"""
        with patch('sys.argv', ['config_loader.py']):
            args = parse_args()
            self.assertIsNone(args.config_dir)

    def test_parse_args_with_config_dir(self):
        """--config-dir引数ありでparse_argsをテスト"""
        with patch('sys.argv', ['config_loader.py', '--config-dir', '/test/path']):
            args = parse_args()
            self.assertEqual(args.config_dir, '/test/path')

    def test_parse_args_with_config_dir_short(self):
        """-c引数ありでparse_argsをテスト"""
        with patch('sys.argv', ['config_loader.py', '-c', '/test/path']):
            args = parse_args()
            self.assertEqual(args.config_dir, '/test/path')

    def test_load_config_custom_dir(self):
        """カスタムディレクトリ指定でload_configをテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # テスト用設定ファイルを作成
            config_file = os.path.join(tmpdir, "setting.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_config, f)
            
            # 設定を読み込み
            config = load_config(tmpdir)
            
            # 結果を検証
            self.assertEqual(config["CharacterName"], "TestCharacter")
            self.assertEqual(config["LLMProvider"], "openai")
            self.assertEqual(config["ports"]["CocoroCore"], 55601)

    def test_load_config_file_not_found(self):
        """存在しないディレクトリを指定した場合のテスト"""
        # 存在しないディレクトリを指定した場合は空の辞書が返される
        config = load_config("/nonexistent/path")
        self.assertEqual(config, {})

    def test_load_config_invalid_json(self):
        """無効なJSONファイルを指定した場合のテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 無効なJSONファイルを作成
            config_file = os.path.join(tmpdir, "setting.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("invalid json content")
            
            # 空の辞書が返されることを確認
            config = load_config(tmpdir)
            self.assertEqual(config, {})

    @patch('sys.frozen', True, create=True)
    @patch('sys.executable', '/test/app.exe')
    @patch('os.path.exists')
    def test_load_config_frozen_app(self, mock_exists):
        """PyInstallerでパッケージ化されたアプリでのテスト"""
        # 設定ファイルが存在することをモック
        mock_exists.return_value = True
        
        # ファイル内容をモック
        with patch('builtins.open', new_callable=mock_open) as mock_file:
            mock_file.return_value.read.return_value = json.dumps(self.test_config)
            # json.loadも適切な値を返すようにモック
            with patch('json.load') as mock_json_load:
                mock_json_load.return_value = self.test_config
                
                # 設定を読み込み
                config = load_config()
                
                # ファイルが開かれることを確認（パス形式は環境依存）
                mock_file.assert_called_once()
                args, kwargs = mock_file.call_args
                self.assertTrue(args[0].endswith('UserData/setting.json') or args[0].endswith('UserData\\setting.json'))
                self.assertEqual(args[1], 'r')
                self.assertEqual(kwargs['encoding'], 'utf-8')
                self.assertEqual(config["CharacterName"], "TestCharacter")

    @patch('sys.frozen', False, create=True)
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_config_script_mode(self, mock_file, mock_exists):
        """通常のPythonスクリプトとして実行した場合のテスト"""
        # 設定ファイルが存在することをモック
        mock_exists.return_value = True
        # ファイル内容をモック
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        # 設定を読み込み
        config = load_config()
        
        # ファイルが開かれることを確認
        mock_file.assert_called()
        self.assertEqual(config["CharacterName"], "TestCharacter")

    def test_load_config_empty_file(self):
        """空のファイルを指定した場合のテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 空のファイルを作成
            config_file = os.path.join(tmpdir, "setting.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("")
            
            # 空の辞書が返されることを確認
            config = load_config(tmpdir)
            self.assertEqual(config, {})


if __name__ == '__main__':
    unittest.main()