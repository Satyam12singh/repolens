class RepolensCli < Formula
  desc "Instant clarity on any codebase — navigate imports, trace functions, and get AI answers in one terminal view"
  homepage "https://github.com/Satyam12singh/repolens"
  url "https://files.pythonhosted.org/packages/9f/7b/7b73c449cfd89e2d289ba58747801c3d00dfe034620eff9ef3a204a3bf78/repolens_cli-0.1.1.tar.gz"
  sha256 "ca07e9c25a62613154d4121922c3d93b573bf04df8c9182f63e717dfc6245688"
  license "MIT"
  version "0.1.1"

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
