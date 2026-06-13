class Repolens < Formula
  include Language::Python::Virtualenv

  desc "Instant clarity on any codebase — navigate imports, trace functions, and get AI answers in one terminal view"
  homepage "https://github.com/Satyam12singh/repolens"
  url "https://files.pythonhosted.org/packages/7f/36/c9cc50e3fef1c5a045ce158dccf72b17abcca3c16f3c59aebc73d576852b/repolens_cli-0.1.0.tar.gz"
  sha256 "1f0eb34ebb55c8edfcf884f8bfff9575d1f66b3f926e53c4a6d0280a3bafe202"
  license "MIT"
  version "0.1.0"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install "repolens-cli==#{version}"
    bin.install_symlink libexec/"bin/repolens"
  end

  test do
    assert_match "RepoLens", shell_output("#{bin}/repolens --help")
  end
end
