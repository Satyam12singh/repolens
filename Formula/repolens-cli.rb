class RepolensCli < Formula
  desc "Instant clarity on any codebase — navigate imports, trace functions, and get AI answers in one terminal view"
  homepage "https://github.com/Satyam12singh/repolens"
  url "https://files.pythonhosted.org/packages/24/c9/07b495143cabcb190f1c7cd1df870f21a4cb48a630942aef1c7f83e68728/repolens_cli-0.2.1.tar.gz"
  sha256 "e3f443bd7362372cf3a808ca2727d6d3514621e63484015510bd7bdb1fd422e5"
  license "MIT"
  version "0.2.1"

  depends_on "python@3.12"

  def install
    python3 = Formula["python@3.12"].opt_bin/"python3.12"
    system python3, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--no-cache-dir", "repolens-cli==#{version}"
    bin.install_symlink libexec/"bin/repolens"
  end

  test do
    assert_match "RepoLens", shell_output("#{bin}/repolens --help 2>&1")
  end
end
