class Repolens < Formula
  include Language::Python::Virtualenv

  desc "Instant clarity on any codebase — navigate imports, trace functions, and get AI answers in one terminal view"
  homepage "https://github.com/Satyam12singh/repolens"
  url "https://files.pythonhosted.org/packages/source/r/repolens/repolens-0.1.0.tar.gz"
  sha256 "FILL_IN_AFTER_PYPI_PUBLISH"
  license "MIT"

  depends_on "python@3.12"

  # Run this once after publishing to PyPI to auto-generate these resource blocks:
  #   pip install homebrew-pypi-poet
  #   poet repolens
  resource "annotated-types" do
    url "https://files.pythonhosted.org/packages/source/a/annotated_types/annotated_types-0.7.0.tar.gz"
    sha256 "FILL_IN"
  end

  resource "anyio" do
    url "https://files.pythonhosted.org/packages/source/a/anyio/anyio-4.9.0.tar.gz"
    sha256 "FILL_IN"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/source/c/certifi/certifi-2025.1.31.tar.gz"
    sha256 "FILL_IN"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/source/c/charset_normalizer/charset_normalizer-3.4.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "distro" do
    url "https://files.pythonhosted.org/packages/source/d/distro/distro-1.9.0.tar.gz"
    sha256 "FILL_IN"
  end

  resource "h11" do
    url "https://files.pythonhosted.org/packages/source/h/h11/h11-0.14.0.tar.gz"
    sha256 "FILL_IN"
  end

  resource "httpcore" do
    url "https://files.pythonhosted.org/packages/source/h/httpcore/httpcore-1.0.7.tar.gz"
    sha256 "FILL_IN"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.28.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/source/i/idna/idna-3.10.tar.gz"
    sha256 "FILL_IN"
  end

  resource "jiter" do
    url "https://files.pythonhosted.org/packages/source/j/jiter/jiter-0.8.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "linkify-it-py" do
    url "https://files.pythonhosted.org/packages/source/l/linkify_it_py/linkify_it_py-2.0.3.tar.gz"
    sha256 "FILL_IN"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/source/m/markdown_it_py/markdown_it_py-3.0.0.tar.gz"
    sha256 "FILL_IN"
  end

  resource "mdit-py-plugins" do
    url "https://files.pythonhosted.org/packages/source/m/mdit_py_plugins/mdit_py_plugins-0.4.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/source/m/mdurl/mdurl-0.1.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "openai" do
    url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.59.9.tar.gz"
    sha256 "FILL_IN"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.10.5.tar.gz"
    sha256 "FILL_IN"
  end

  resource "pydantic-core" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic_core/pydantic_core-2.27.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.19.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "python-dotenv" do
    url "https://files.pythonhosted.org/packages/source/p/python_dotenv/python_dotenv-1.0.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.32.3.tar.gz"
    sha256 "FILL_IN"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "FILL_IN"
  end

  resource "sniffio" do
    url "https://files.pythonhosted.org/packages/source/s/sniffio/sniffio-1.3.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "textual" do
    url "https://files.pythonhosted.org/packages/source/t/textual/textual-2.1.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "tqdm" do
    url "https://files.pythonhosted.org/packages/source/t/tqdm/tqdm-4.67.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/source/t/typing_extensions/typing_extensions-4.12.2.tar.gz"
    sha256 "FILL_IN"
  end

  resource "uc-micro-py" do
    url "https://files.pythonhosted.org/packages/source/u/uc_micro_py/uc_micro_py-1.0.3.tar.gz"
    sha256 "FILL_IN"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/source/u/urllib3/urllib3-2.3.0.tar.gz"
    sha256 "FILL_IN"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "RepoLens", shell_output("#{bin}/repolens --help")
  end
end
