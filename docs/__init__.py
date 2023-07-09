def serve(docs_dir: str = ".", delay: int = 1):
    from livereload import Server, shell

    build_dir = f"{docs_dir}/_build"
    build_cmd = f"sphinx-build {docs_dir} {build_dir}"
    server = Server()
    server.watch("**/*.rst", shell(build_cmd), delay=delay)
    server.watch("**/*.md", shell(build_cmd), delay=delay)
    server.watch("**/*.py", shell(build_cmd), delay=delay)
    server.watch("_static/*", shell(build_cmd), delay=delay)
    server.watch("_templates/*", shell(build_cmd), delay=delay)
    server.watch("../poethepoet/**/*", shell(build_cmd), delay=delay)
    server.serve(root=f"{build_dir}")
