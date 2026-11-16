import argparse
from .common import config

def main():
    parser=argparse.ArgumentParser(description="Prototipo CNN para comandos ingleses y visor PDF")
    parser.add_argument("--config",default="config.json")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("download");p.add_argument("--zip")
    sub.add_parser("prepare")
    p=sub.add_parser("train");p.add_argument("--smoke",action="store_true")
    p=sub.add_parser("evaluate");p.add_argument("--model-dir",default="models/full")
    sub.add_parser("gui");sub.add_parser("demo")
    args=parser.parse_args()
    if args.command=="download":
        from .download import download
        download(args.zip)
    elif args.command=="prepare":
        from .prepare import prepare
        prepare(config(args.config))
    elif args.command=="train":
        from .train import train
        train(config(args.config),args.smoke)
    elif args.command=="evaluate":
        from .evaluate import evaluate
        evaluate(args.model_dir)
    elif args.command=="gui":
        from .gui import launch
        launch()
    elif args.command=="demo":
        from .gui import demo
        print(demo())

if __name__=="__main__":main()
